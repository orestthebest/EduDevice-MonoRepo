"""Stundenplan (Ziel-M-4): GET /timetable/{user_id}"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, role_of
from app.schemas import TimetableOut
from app.services.access import student_class_ids

router = APIRouter(prefix="/timetable", tags=["Stundenplan"])
WEEKDAY_ORDER = {d: i for i, d in enumerate(m.WEEKDAYS)}


@router.get("/{user_id}", response_model=list[TimetableOut])
def get_timetable(user_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    if role_of(current) != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Nur eigener Stundenplan einsehbar")
    target = db.get(m.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    query = (db.query(m.TimetableEntry, m.Subject.name, m.SchoolClass.name)
             .join(m.ClassSubject, m.TimetableEntry.class_subject_id == m.ClassSubject.id)
             .join(m.Subject, m.ClassSubject.subject_id == m.Subject.id)
             .join(m.SchoolClass, m.ClassSubject.class_id == m.SchoolClass.id))
    role = role_of(target)
    if role == "schueler":
        query = query.filter(m.ClassSubject.class_id.in_(student_class_ids(db, user_id)))
    elif role == "lehrkraft":
        query = query.filter(m.ClassSubject.teacher_id == user_id)
    else:
        return []

    rows = sorted(query.all(), key=lambda r: (WEEKDAY_ORDER.get(r[0].weekday, 9), r[0].start_time))
    return [TimetableOut(id=t.id, class_subject_id=t.class_subject_id, subject=subject, class_name=cls,
                         weekday=t.weekday, start_time=t.start_time.strftime("%H:%M"),
                         end_time=t.end_time.strftime("%H:%M"), room=t.room)
            for t, subject, cls in rows]
