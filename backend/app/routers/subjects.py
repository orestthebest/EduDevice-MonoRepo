"""
Faecher (ersetzt frontend/src/lib/server/subjects.js).
"Fach" in der WebApp = ein Eintrag in class_subjects (Klasse + Fach + Lehrkraft).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.schemas import StudentIdIn, StudentOut, SubjectCreateIn, SubjectOut
from app.services.access import (filter_subjects_for_user, own_subject_or_403, student_out,
                                 subject_for_user_or_404, subject_query, to_subject_out)
from app.services.files import delete_stored_file

router = APIRouter(prefix="/subjects", tags=["Faecher"])


@router.get("", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    rows = filter_subjects_for_user(subject_query(db), current).order_by(m.SchoolClass.name, m.Subject.name).all()
    return [to_subject_out(r) for r in rows]


@router.get("/names", response_model=list[str])
def subject_names(db: Session = Depends(get_db), current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Alle Fachnamen im Katalog (Vorschlaege beim Tippen)."""
    return [r[0] for r in db.query(m.Subject.name).order_by(m.Subject.name)]


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(data: SubjectCreateIn, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("lehrkraft"))):
    """1. Fachname suchen/anlegen  2. class_subjects anlegen  3. SchuelerInnen der Klasse eintragen."""
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bitte einen Fachnamen eingeben")
    if db.get(m.SchoolClass, data.class_id) is None:
        raise HTTPException(status_code=400, detail="Diese Klasse existiert nicht")
    duplicate = HTTPException(status_code=409, detail=f'Diese Klasse hat das Fach "{name}" schon')
    try:
        subject = db.query(m.Subject).filter(m.Subject.name == name).first()
        if subject is None:
            subject = m.Subject(name=name)
            db.add(subject)
            db.flush()
        if db.query(m.ClassSubject).filter_by(class_id=data.class_id, subject_id=subject.id).first():
            raise duplicate
        cs = m.ClassSubject(class_id=data.class_id, subject_id=subject.id, teacher_id=current.id)
        db.add(cs)
        db.flush()
        students = (db.query(m.StudentClass.student_id)
                    .join(m.User, m.User.id == m.StudentClass.student_id)
                    .filter(m.StudentClass.class_id == data.class_id, m.User.role == "schueler"))
        for (sid,) in students:
            db.add(m.ClassSubjectStudent(class_subject_id=cs.id, student_id=sid))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise duplicate
    except HTTPException:
        db.rollback()
        raise
    return subject_for_user_or_404(db, cs.id, current)


@router.get("/{cs_id}", response_model=SubjectOut)
def get_subject(cs_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    return subject_for_user_or_404(db, cs_id, current)


@router.delete("/{cs_id}")
def delete_subject(cs_id: int, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("lehrkraft"))):
    """Nur wenn keine Noten, Quizzes, Hausaufgaben oder Stundenplan dranhaengen.
    Materialien (+ Dateien) und SchuelerInnenliste werden mitgeloescht."""
    own_subject_or_403(db, cs_id, current)
    used = sum(db.query(func.count(model.id)).filter(model.class_subject_id == cs_id).scalar()
               for model in (m.Grade, m.Quiz, m.TimetableEntry, m.Homework))
    if used > 0:
        raise HTTPException(status_code=409,
                            detail="Dieses Fach hat schon Noten, Quizzes, Hausaufgaben oder einen Stundenplan")
    stored = [r[0] for r in db.query(m.Material.stored_name).filter(m.Material.class_subject_id == cs_id)]
    try:
        db.query(m.Material).filter(m.Material.class_subject_id == cs_id).delete()
        db.query(m.ClassSubjectStudent).filter(m.ClassSubjectStudent.class_subject_id == cs_id).delete()
        db.query(m.ClassSubject).filter(m.ClassSubject.id == cs_id).delete()
        db.commit()
    except IntegrityError:   # z. B. period_grades haengen dran (kein CASCADE)
        db.rollback()
        raise HTTPException(status_code=409, detail="Fach wird noch verwendet und kann nicht geloescht werden")
    for name in stored:
        delete_stored_file(name)
    return {"status": "geloescht", "id": cs_id, "deleted_files": len(stored)}


# ---------------- SchuelerInnen eines Fachs (nur Lehrkraft des Fachs) ----------------
def addable_students(db: Session, cs: m.ClassSubject) -> list[m.User]:
    """Nur SchuelerInnen aus der Klasse des Fachs, die noch nicht eingetragen sind."""
    already = select(m.ClassSubjectStudent.student_id).where(m.ClassSubjectStudent.class_subject_id == cs.id)
    return (db.query(m.User).join(m.StudentClass, m.StudentClass.student_id == m.User.id)
            .filter(m.StudentClass.class_id == cs.class_id, m.User.role == "schueler", m.User.id.not_in(already))
            .order_by(m.User.last_name, m.User.first_name).all())


@router.get("/{cs_id}/students", response_model=list[StudentOut])
def subject_students(cs_id: int, db: Session = Depends(get_db),
                     current: m.User = Depends(require_roles("lehrkraft"))):
    own_subject_or_403(db, cs_id, current)
    users = (db.query(m.User).join(m.ClassSubjectStudent, m.ClassSubjectStudent.student_id == m.User.id)
             .filter(m.ClassSubjectStudent.class_subject_id == cs_id)
             .order_by(m.User.last_name, m.User.first_name).all())
    result = []
    for u in users:
        names = [r[0] for r in db.query(m.SchoolClass.name)
                 .join(m.StudentClass, m.StudentClass.class_id == m.SchoolClass.id)
                 .filter(m.StudentClass.student_id == u.id)]
        result.append(student_out(u, ", ".join(names) or None))
    return result


@router.get("/{cs_id}/addable-students", response_model=list[StudentOut])
def subject_addable(cs_id: int, db: Session = Depends(get_db),
                    current: m.User = Depends(require_roles("lehrkraft"))):
    cs = own_subject_or_403(db, cs_id, current)
    return [student_out(u) for u in addable_students(db, cs)]


@router.post("/{cs_id}/students", status_code=201)
def subject_add_student(cs_id: int, data: StudentIdIn, db: Session = Depends(get_db),
                        current: m.User = Depends(require_roles("lehrkraft"))):
    cs = own_subject_or_403(db, cs_id, current)
    if data.student_id not in {u.id for u in addable_students(db, cs)}:
        raise HTTPException(status_code=400, detail="SchuelerIn nicht gefunden oder schon eingetragen")
    db.add(m.ClassSubjectStudent(class_subject_id=cs_id, student_id=data.student_id))
    db.commit()
    return {"status": "hinzugefuegt", "class_subject_id": cs_id, "student_id": data.student_id}


@router.delete("/{cs_id}/students/{student_id}")
def subject_remove_student(cs_id: int, student_id: int, db: Session = Depends(get_db),
                           current: m.User = Depends(require_roles("lehrkraft"))):
    own_subject_or_403(db, cs_id, current)
    db.query(m.ClassSubjectStudent).filter_by(class_subject_id=cs_id, student_id=student_id).delete()
    db.commit()
    return {"status": "entfernt", "class_subject_id": cs_id, "student_id": student_id}
