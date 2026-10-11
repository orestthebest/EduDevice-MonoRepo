"""Hausaufgaben (Ziel-M-4): GET /homework/{subject_id}, POST /homework/confirm"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, require_roles, role_of
from app.schemas import HomeworkConfirmIn, HomeworkOut
from app.services.access import get_class_subject_or_404, student_class_ids

router = APIRouter(prefix="/homework", tags=["Hausaufgaben"])


@router.get("/{subject_id}", response_model=list[HomeworkOut])
def get_homework(subject_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    query = db.query(m.Homework).join(m.ClassSubject, m.Homework.class_subject_id == m.ClassSubject.id) \
              .filter(m.ClassSubject.subject_id == subject_id)
    role = role_of(current)
    if role == "schueler":
        query = query.filter(m.ClassSubject.class_id.in_(student_class_ids(db, current.id)))
    elif role == "lehrkraft":
        query = query.filter(m.ClassSubject.teacher_id == current.id)
    return query.order_by(m.Homework.due_date).all()


@router.post("/confirm")
def confirm_homework(data: HomeworkConfirmIn, db: Session = Depends(get_db),
                     current: m.User = Depends(require_roles("schueler"))):
    hw = db.get(m.Homework, data.homework_id)
    if hw is None:
        raise HTTPException(status_code=404, detail="Hausaufgabe nicht gefunden")
    cs = get_class_subject_or_404(db, hw.class_subject_id)
    if cs.class_id not in student_class_ids(db, current.id):
        raise HTTPException(status_code=403, detail="Diese Hausaufgabe gehoert nicht zu Ihrer Klasse")
    conf = db.query(m.HomeworkConfirmation).filter_by(homework_id=hw.id, student_id=current.id).first()
    if conf is None:
        conf = m.HomeworkConfirmation(homework_id=hw.id, student_id=current.id)
        db.add(conf)
    conf.confirmed_at = datetime.now()
    conf.status = "confirmed"
    db.commit()
    return {"status": "bestaetigt", "homework_id": hw.id}
