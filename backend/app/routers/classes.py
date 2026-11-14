"""Klassen und Klassenzuteilung (ersetzt frontend/src/lib/server/classes.js)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import require_roles, role_of
from app.schemas import ClassOut, ClassTeacherIn, StudentIdIn, StudentOut
from app.services.access import student_out

router = APIRouter(prefix="/classes", tags=["Klassen"])


def class_out(db: Session, c: m.SchoolClass, label: str) -> ClassOut:
    """Klasse mit Klassenvorstand (V4.11)."""
    kv = db.get(m.User, c.class_teacher_id) if c.class_teacher_id else None
    return ClassOut(id=c.id, name=c.name, school_year_id=c.school_year_id, school_year=label,
                    class_teacher_id=c.class_teacher_id,
                    class_teacher_name=f"{kv.first_name} {kv.last_name}" if kv else None)


def class_or_404(db: Session, class_id: int) -> ClassOut:
    row = (db.query(m.SchoolClass, m.SchoolYear.label)
           .join(m.SchoolYear, m.SchoolYear.id == m.SchoolClass.school_year_id)
           .filter(m.SchoolClass.id == class_id).first())
    if row is None:
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    c, label = row
    return class_out(db, c, label)


def assignable_students(db: Session, school_year_id: int) -> list[m.User]:
    """Alle SchuelerInnen, die in diesem Schuljahr noch in KEINER Klasse sind."""
    in_year = (exists().where(m.StudentClass.student_id == m.User.id)
               .where(m.StudentClass.class_id == m.SchoolClass.id)
               .where(m.SchoolClass.school_year_id == school_year_id))
    return (db.query(m.User).filter(m.User.role == "schueler", ~in_year)
            .order_by(m.User.last_name, m.User.first_name).all())


@router.get("", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db), current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Alle Klassen, neuestes Schuljahr zuerst (Lehrkraft braucht sie fuer 'New subject')."""
    rows = (db.query(m.SchoolClass, m.SchoolYear.label)
            .join(m.SchoolYear, m.SchoolYear.id == m.SchoolClass.school_year_id)
            .order_by(m.SchoolYear.start_date.desc(), m.SchoolClass.name).all())
    return [class_out(db, c, label) for c, label in rows]


@router.get("/{class_id}", response_model=ClassOut)
def get_class(class_id: int, db: Session = Depends(get_db), current: m.User = Depends(require_roles("admin"))):
    return class_or_404(db, class_id)


@router.patch("/{class_id}", response_model=ClassOut)
def set_class_teacher(class_id: int, data: ClassTeacherIn, db: Session = Depends(get_db),
                      current: m.User = Depends(require_roles("admin"))):
    """Klassenvorstand setzen oder mit null entfernen. Muss eine Lehrkraft sein, sonst 400."""
    c = db.get(m.SchoolClass, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Klasse nicht gefunden")
    if data.class_teacher_id is not None:
        teacher = db.get(m.User, data.class_teacher_id)
        if teacher is None or role_of(teacher) != "lehrkraft":
            raise HTTPException(status_code=400, detail="Klassenvorstand muss eine Lehrkraft sein")
    c.class_teacher_id = data.class_teacher_id
    db.commit()
    return class_or_404(db, class_id)


@router.get("/{class_id}/students", response_model=list[StudentOut])
def class_students(class_id: int, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("admin"))):
    class_or_404(db, class_id)
    users = (db.query(m.User).join(m.StudentClass, m.StudentClass.student_id == m.User.id)
             .filter(m.StudentClass.class_id == class_id)
             .order_by(m.User.last_name, m.User.first_name).all())
    return [student_out(u) for u in users]


@router.get("/{class_id}/assignable-students", response_model=list[StudentOut])
def class_assignable(class_id: int, db: Session = Depends(get_db),
                     current: m.User = Depends(require_roles("admin"))):
    c = class_or_404(db, class_id)
    return [student_out(u) for u in assignable_students(db, c.school_year_id)]


@router.post("/{class_id}/students", status_code=201)
def add_student(class_id: int, data: StudentIdIn, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("admin"))):
    """SchuelerIn in die Klasse + automatisch in alle Faecher der Klasse (eine Transaktion)."""
    c = class_or_404(db, class_id)
    if data.student_id not in {u.id for u in assignable_students(db, c.school_year_id)}:
        raise HTTPException(status_code=400,
                            detail="SchuelerIn nicht gefunden oder in diesem Schuljahr schon in einer Klasse")
    try:
        db.add(m.StudentClass(student_id=data.student_id, class_id=class_id))
        for (cs_id,) in db.query(m.ClassSubject.id).filter(m.ClassSubject.class_id == class_id):
            if not db.query(m.ClassSubjectStudent).filter_by(class_subject_id=cs_id,
                                                             student_id=data.student_id).first():
                db.add(m.ClassSubjectStudent(class_subject_id=cs_id, student_id=data.student_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "hinzugefuegt", "class_id": class_id, "student_id": data.student_id}


@router.delete("/{class_id}/students/{student_id}")
def remove_student(class_id: int, student_id: int, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("admin"))):
    """SchuelerIn aus der Klasse + aus allen Faechern dieser Klasse (eine Transaktion)."""
    class_or_404(db, class_id)
    try:
        cs_ids = select(m.ClassSubject.id).where(m.ClassSubject.class_id == class_id)
        db.query(m.ClassSubjectStudent).filter(
            m.ClassSubjectStudent.student_id == student_id,
            m.ClassSubjectStudent.class_subject_id.in_(cs_ids)).delete(synchronize_session=False)
        db.query(m.StudentClass).filter_by(class_id=class_id, student_id=student_id).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "entfernt", "class_id": class_id, "student_id": student_id}
