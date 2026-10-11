"""Anwesenheit (Ziel-M-4): GET /attendance/{class_id}/{date}, POST /attendance"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import require_roles, role_of
from app.schemas import AttendanceIn, AttendanceOut
from app.services.access import check_student_in_class, check_teaches, get_class_subject_or_404

router = APIRouter(prefix="/attendance", tags=["Anwesenheit"])


@router.get("/{class_id}/{date}", response_model=list[AttendanceOut])
def get_attendance(class_id: int, date: date_type, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    query = (db.query(m.Attendance)
             .join(m.Lesson, m.Attendance.lesson_id == m.Lesson.id)
             .join(m.TimetableEntry, m.Lesson.timetable_id == m.TimetableEntry.id)
             .join(m.ClassSubject, m.TimetableEntry.class_subject_id == m.ClassSubject.id)
             .filter(m.ClassSubject.class_id == class_id, m.Lesson.date == date))
    if role_of(current) == "lehrkraft":
        query = query.filter(m.ClassSubject.teacher_id == current.id)
    return query.all()


@router.post("", response_model=AttendanceOut)
def add_attendance(entry: AttendanceIn, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    lesson = db.get(m.Lesson, entry.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Unterrichtsstunde nicht gefunden")
    tt = db.get(m.TimetableEntry, lesson.timetable_id)
    cs = get_class_subject_or_404(db, tt.class_subject_id)
    check_teaches(current, cs)
    check_student_in_class(db, entry.student_id, cs.class_id)
    # pro SchuelerIn und Stunde genau ein Eintrag -> aktualisieren statt doppelt anlegen
    record = db.query(m.Attendance).filter_by(student_id=entry.student_id, lesson_id=entry.lesson_id).first()
    if record is None:
        record = m.Attendance(student_id=entry.student_id, lesson_id=entry.lesson_id)
        db.add(record)
    record.status = entry.status
    db.commit()
    db.refresh(record)
    return record
