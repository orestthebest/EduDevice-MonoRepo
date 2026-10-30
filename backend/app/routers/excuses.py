"""Entschuldigungssystem (O-3, Schema V4.6).
SchuelerIn entschuldigt eigene Fehlstunden, der Klassenvorstand (classes.class_teacher_id)
nimmt an oder lehnt ab. Welche Fehlstunden zu einer Entschuldigung gehoeren, steht in
attendance.excuse_id (keine Extra-Tabelle).

"Unentschuldigt" = attendance.status abwesend/verspaetet UND (keine Entschuldigung ODER abgelehnt).
Abgelehnte Fehlstunden koennen neu eingereicht werden (excuse_id wird ueberschrieben)."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, aliased

from app import models as m
from app.core.database import get_db
from app.core.security import require_roles, role_of
from app.schemas import AbsenceOut, ExcuseIn, ExcuseOut, ExcuseReviewIn

router = APIRouter(tags=["Entschuldigungen"])


# ---------------- Hilfsfunktionen ----------------
def absence_query(db: Session):
    """Fehlstunde mit Datum, Uhrzeit, Fach und Status der Entschuldigung."""
    return (db.query(m.Attendance, m.Lesson.date, m.TimetableEntry.start_time, m.TimetableEntry.end_time,
                     m.Subject.name, m.Excuse.status)
            .join(m.Lesson, m.Lesson.id == m.Attendance.lesson_id)
            .join(m.TimetableEntry, m.TimetableEntry.id == m.Lesson.timetable_id)
            .join(m.ClassSubject, m.ClassSubject.id == m.TimetableEntry.class_subject_id)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .outerjoin(m.Excuse, m.Excuse.id == m.Attendance.excuse_id))


def unexcused_filter(query, student_id: int):
    return query.filter(m.Attendance.student_id == student_id,
                        m.Attendance.status.in_(m.ABSENCE_STATUS),
                        m.Lesson.cancelled.is_(False),
                        or_(m.Attendance.excuse_id.is_(None), m.Excuse.status == "rejected"))


def to_absence_out(row) -> AbsenceOut:
    att, day, start, end, subject, excuse_status = row
    return AbsenceOut(attendance_id=att.id, date=day, start_time=start, end_time=end, subject_name=subject,
                      status=att.status, excuse_id=att.excuse_id, excuse_status=excuse_status)


def excuse_out(db: Session, exc: m.Excuse, class_name: Optional[str] = None) -> ExcuseOut:
    rows = (absence_query(db).filter(m.Attendance.excuse_id == exc.id)
            .order_by(m.Lesson.date, m.TimetableEntry.start_time).all())
    student = db.get(m.User, exc.student_id)
    reviewer = db.get(m.User, exc.reviewed_by) if exc.reviewed_by else None
    return ExcuseOut(id=exc.id, student_id=exc.student_id,
                     student_name=f"{student.first_name} {student.last_name}", class_name=class_name,
                     date_from=exc.date_from, date_to=exc.date_to, reason=exc.reason, status=exc.status,
                     teacher_comment=exc.teacher_comment, reviewed_by=exc.reviewed_by,
                     reviewed_by_name=f"{reviewer.first_name} {reviewer.last_name}" if reviewer else None,
                     reviewed_at=exc.reviewed_at, submitted_at=exc.submitted_at,
                     absences=[to_absence_out(r) for r in rows])


def class_teacher_class_name(db: Session, student_id: int, teacher: m.User) -> Optional[str]:
    """Name der Klasse, in der `teacher` Klassenvorstand von `student_id` ist (Admin: irgendeine Klasse).
    None = kein Klassenvorstand dieser SchuelerIn."""
    q = (db.query(m.SchoolClass.name)
         .join(m.StudentClass, m.StudentClass.class_id == m.SchoolClass.id)
         .filter(m.StudentClass.student_id == student_id))
    if role_of(teacher) != "admin":
        q = q.filter(m.SchoolClass.class_teacher_id == teacher.id)
    row = q.order_by(m.SchoolClass.id.desc()).first()
    return row[0] if row else None


# ---------------- SchuelerIn ----------------
@router.get("/attendance/me", response_model=list[AbsenceOut])
def my_absences(unexcused: bool = False, db: Session = Depends(get_db),
                current: m.User = Depends(require_roles("schueler"))):
    """Eigene Fehlstunden (abwesend/verspaetet). unexcused=true -> nur die, die man noch entschuldigen kann."""
    q = absence_query(db)
    if unexcused:
        q = unexcused_filter(q, current.id)
    else:
        q = q.filter(m.Attendance.student_id == current.id, m.Attendance.status.in_(m.ABSENCE_STATUS))
    rows = q.order_by(m.Lesson.date.desc(), m.TimetableEntry.start_time).all()
    return [to_absence_out(r) for r in rows]


@router.post("/excuses", response_model=ExcuseOut, status_code=201)
def create_excuse(data: ExcuseIn, db: Session = Depends(get_db),
                  current: m.User = Depends(require_roles("schueler"))):
    """Entschuldigung fuer eigene, noch unentschuldigte Fehlstunden einreichen."""
    ids = set(data.attendance_ids)
    rows = (unexcused_filter(absence_query(db), current.id)
            .filter(m.Attendance.id.in_(ids))
            .with_for_update().all())                         # gleichzeitiges Einreichen verhindern
    if len(rows) != len(ids):
        raise HTTPException(status_code=400,
                            detail="Mindestens eine Fehlstunde gehoert nicht dir oder ist schon entschuldigt")
    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Bitte einen Grund angeben")

    days = [r[1] for r in rows]
    exc = m.Excuse(student_id=current.id, date_from=min(days), date_to=max(days),
                   reason=reason, status="pending")
    db.add(exc)
    db.flush()                                                   # exc.id wird vergeben
    for r in rows:
        r[0].excuse_id = exc.id                                  # abgelehnte werden ueberschrieben
    db.commit()
    db.refresh(exc)
    return excuse_out(db, exc)


@router.get("/excuses/me", response_model=list[ExcuseOut])
def my_excuses(db: Session = Depends(get_db), current: m.User = Depends(require_roles("schueler"))):
    excuses = (db.query(m.Excuse).filter(m.Excuse.student_id == current.id)
               .order_by(m.Excuse.submitted_at.desc(), m.Excuse.id.desc()).all())
    return [excuse_out(db, e) for e in excuses]


# ---------------- Klassenvorstand ----------------
@router.get("/excuses/class-teacher", response_model=list[ExcuseOut])
def class_teacher_excuses(status: Optional[Literal["pending", "accepted", "rejected"]] = None,
                          db: Session = Depends(get_db),
                          current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Entschuldigungen der SchuelerInnen aus Klassen, in denen ich Klassenvorstand bin (Admin: alle)."""
    sc = aliased(m.SchoolClass)
    q = (db.query(m.Excuse, sc.name)
         .join(m.StudentClass, m.StudentClass.student_id == m.Excuse.student_id)
         .join(sc, sc.id == m.StudentClass.class_id))
    if role_of(current) != "admin":
        q = q.filter(sc.class_teacher_id == current.id)
    if status:
        q = q.filter(m.Excuse.status == status)
    seen, result = set(), []
    for exc, class_name in q.order_by(m.Excuse.submitted_at.desc(), m.Excuse.id.desc()).all():
        if exc.id not in seen:                                   # SchuelerIn in mehreren Klassen -> nur einmal
            seen.add(exc.id)
            result.append(excuse_out(db, exc, class_name))
    return result


@router.patch("/excuses/{excuse_id}", response_model=ExcuseOut)
def review_excuse(excuse_id: int, data: ExcuseReviewIn, db: Session = Depends(get_db),
                  current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Annehmen oder ablehnen. Nur der Klassenvorstand der SchuelerIn (oder Admin), nur wenn noch offen."""
    exc = db.get(m.Excuse, excuse_id)
    class_name = class_teacher_class_name(db, exc.student_id, current) if exc else None
    if exc is None or class_name is None:
        raise HTTPException(status_code=404, detail="Entschuldigung nicht gefunden")
    if exc.status != "pending":
        raise HTTPException(status_code=409, detail="Diese Entschuldigung wurde schon bearbeitet")
    comment = (data.teacher_comment or "").strip()
    exc.status = data.status
    exc.teacher_comment = comment or None
    exc.reviewed_by = current.id
    exc.reviewed_at = datetime.now().replace(microsecond=0)
    db.commit()
    db.refresh(exc)
    return excuse_out(db, exc, class_name)
