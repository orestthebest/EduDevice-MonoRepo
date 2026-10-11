"""Noten (Ziel-M-4): GET /grades/{student_id}, POST /grades"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, require_roles, role_of
from app.schemas import GradeIn, GradeOut
from app.services.access import check_student_in_class, check_teaches, get_class_subject_or_404

router = APIRouter(prefix="/grades", tags=["Noten"])


@router.get("/{student_id}", response_model=list[GradeOut])
def get_grades(student_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    query = db.query(m.Grade).filter(m.Grade.student_id == student_id)
    role = role_of(current)
    if role == "schueler" and current.id != student_id:
        raise HTTPException(status_code=403, detail="Nur eigene Noten einsehbar")
    if role == "lehrkraft":   # nur Noten aus eigenen Faechern
        query = query.join(m.ClassSubject, m.Grade.class_subject_id == m.ClassSubject.id) \
                     .filter(m.ClassSubject.teacher_id == current.id)
    return query.order_by(m.Grade.date).all()


@router.post("", response_model=GradeOut, status_code=201)
def add_grade(grade: GradeIn, db: Session = Depends(get_db),
              current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    cs = get_class_subject_or_404(db, grade.class_subject_id)
    check_teaches(current, cs)
    check_student_in_class(db, grade.student_id, cs.class_id)
    new = m.Grade(student_id=grade.student_id, class_subject_id=grade.class_subject_id,
                  category=grade.category, value=grade.value, weight=grade.weight,
                  date=grade.date or date.today(), homework_id=grade.homework_id)
    db.add(new)
    db.commit()
    db.refresh(new)
    return new
