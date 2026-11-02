"""Anwesenheit.
Ziel-M-4: GET /attendance/{class_id}/{date}, POST /attendance
V2.8 (WebApp): GET/PUT /attendance (eine Stunde), GET /attendance/slots, GET /attendance/history"""

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
    if entry.status == "anwesend":
        record.excuse_id = None          # keine veraltete Entschuldigung an einer Anwesenheit
    db.commit()
    db.refresh(record)
    return record


# ================= Anwesenheit pro Stunde fuer die WebApp (V2.8) =================
# Eine Unterrichtsstunde ist im Schema: timetable (Fach + Wochentag + Beginn) + Datum = Zeile in lessons.
# attendance haengt an lessons (UNIQUE student_id + lesson_id) -> keine Schema-Aenderung noetig.
from datetime import time as time_type  # noqa: E402

from sqlalchemy import case, func  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.schemas import (LessonAttendanceIn, LessonAttendanceOut, LessonHistoryOut,  # noqa: E402
                         LessonSlotOut, LessonStudentOut)


def teacher_subject(db: Session, cs_id: int, user: m.User) -> m.ClassSubject:
    """Fach muss existieren (404) und von dieser Lehrkraft unterrichtet werden (403). Admin darf alles."""
    cs = get_class_subject_or_404(db, cs_id)
    check_teaches(user, cs)
    return cs


def weekday_of(day: date_type) -> str:
    if day.weekday() > 4:
        raise HTTPException(status_code=400, detail="Am Wochenende gibt es keinen Unterricht")
    return m.WEEKDAYS[day.weekday()]


def find_slot(db: Session, cs: m.ClassSubject, day: date_type, start: time_type) -> m.TimetableEntry:
    wd = weekday_of(day)
    slot = (db.query(m.TimetableEntry)
            .filter_by(class_subject_id=cs.id, weekday=wd, start_time=start).first())
    if slot is None:
        raise HTTPException(status_code=404,
                            detail=f"Laut Stundenplan hat dieses Fach am {wd} um {start:%H:%M} keine Stunde")
    return slot


def lesson_attendance(db: Session, cs: m.ClassSubject, slot: m.TimetableEntry, day: date_type) -> LessonAttendanceOut:
    lesson = db.query(m.Lesson).filter_by(timetable_id=slot.id, date=day).first()
    records = {}
    if lesson:
        records = {a.student_id: a for a in db.query(m.Attendance).filter_by(lesson_id=lesson.id)}
    enrolled = (db.query(m.User).join(m.ClassSubjectStudent, m.ClassSubjectStudent.student_id == m.User.id)
                .filter(m.ClassSubjectStudent.class_subject_id == cs.id).all())
    enrolled_ids = {u.id for u in enrolled}
    # wer nicht mehr im Fach ist, aber fuer diese Stunde einen Eintrag hat, bleibt sichtbar
    extra = db.query(m.User).filter(m.User.id.in_(set(records) - enrolled_ids)).all() if records else []
    students = []
    for u in sorted(enrolled + extra, key=lambda u: (u.last_name.lower(), u.first_name.lower())):
        rec = records.get(u.id)
        students.append(LessonStudentOut(student_id=u.id, first_name=u.first_name, last_name=u.last_name,
                                         username=u.username, status=rec.status if rec else None,
                                         excuse_id=rec.excuse_id if rec else None,
                                         enrolled=u.id in enrolled_ids))
    return LessonAttendanceOut(class_subject_id=cs.id, date=day, start_time=slot.start_time,
                               end_time=slot.end_time, room=slot.room,
                               lesson_id=lesson.id if lesson else None,
                               cancelled=bool(lesson and lesson.cancelled), students=students)


@router.get("/slots", response_model=list[LessonSlotOut])
def lesson_slots(class_subject_id: int, date: date_type, db: Session = Depends(get_db),
                 current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Welche Stunden hat das Fach an diesem Tag laut Stundenplan? (fuer die Auswahl von start_time)"""
    cs = teacher_subject(db, class_subject_id, current)
    slots = (db.query(m.TimetableEntry).filter_by(class_subject_id=cs.id, weekday=weekday_of(date))
             .order_by(m.TimetableEntry.start_time).all())
    return [LessonSlotOut(timetable_id=s.id, weekday=s.weekday, start_time=s.start_time,
                          end_time=s.end_time, room=s.room) for s in slots]


@router.get("/history", response_model=list[LessonHistoryOut])
def lesson_history(class_subject_id: int, db: Session = Depends(get_db),
                   current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Alle Stunden dieses Fachs, fuer die schon Anwesenheit erfasst wurde (neueste zuerst)."""
    cs = teacher_subject(db, class_subject_id, current)

    def count(status):
        return func.coalesce(func.sum(case((m.Attendance.status == status, 1), else_=0)), 0)

    rows = (db.query(m.Lesson.id, m.Lesson.date, m.TimetableEntry.start_time, m.TimetableEntry.end_time,
                     count("anwesend"), count("abwesend"), count("verspaetet"))
            .join(m.TimetableEntry, m.TimetableEntry.id == m.Lesson.timetable_id)
            .join(m.Attendance, m.Attendance.lesson_id == m.Lesson.id)
            .filter(m.TimetableEntry.class_subject_id == cs.id)
            .group_by(m.Lesson.id, m.Lesson.date, m.TimetableEntry.start_time, m.TimetableEntry.end_time)
            .order_by(m.Lesson.date.desc(), m.TimetableEntry.start_time.desc()).all())
    return [LessonHistoryOut(lesson_id=r[0], date=r[1], start_time=r[2], end_time=r[3],
                             present_count=r[4], absent_count=r[5], late_count=r[6]) for r in rows]


@router.get("", response_model=LessonAttendanceOut)
def get_lesson_attendance(class_subject_id: int, date: date_type, start_time: time_type,
                          db: Session = Depends(get_db),
                          current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Alle SchuelerInnen des Fachs mit ihrem Status fuer diese Stunde (status null = noch nicht erfasst)."""
    cs = teacher_subject(db, class_subject_id, current)
    slot = find_slot(db, cs, date, start_time)
    return lesson_attendance(db, cs, slot, date)


@router.put("", response_model=LessonAttendanceOut)
def save_lesson_attendance(data: LessonAttendanceIn, db: Session = Depends(get_db),
                           current: m.User = Depends(require_roles("lehrkraft", "admin"))):
    """Anwesenheit fuer eine Stunde speichern (anlegen oder korrigieren). Nur mitgeschickte SchuelerInnen
    werden geaendert. Wird jemand auf 'anwesend' gesetzt, faellt eine verknuepfte Entschuldigung weg."""
    cs = teacher_subject(db, data.class_subject_id, current)
    if data.date > date_type.today():
        raise HTTPException(status_code=400, detail="Anwesenheit fuer zukuenftige Stunden geht noch nicht")
    slot = find_slot(db, cs, data.date, data.start_time)

    ids = [e.student_id for e in data.entries]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="Eine SchuelerIn ist doppelt in der Liste")

    lesson = db.query(m.Lesson).filter_by(timetable_id=slot.id, date=data.date).first()
    allowed = {r[0] for r in db.query(m.ClassSubjectStudent.student_id).filter_by(class_subject_id=cs.id)}
    if lesson:   # alte Eintraege von inzwischen ausgetragenen SchuelerInnen duerfen korrigiert werden
        allowed |= {r[0] for r in db.query(m.Attendance.student_id).filter_by(lesson_id=lesson.id)}
    if not set(ids) <= allowed:
        raise HTTPException(status_code=400, detail="Mindestens eine SchuelerIn ist nicht in diesem Fach")

    if lesson is None:
        lesson = m.Lesson(timetable_id=slot.id, date=data.date, cancelled=False)
        db.add(lesson)
        try:
            db.flush()
        except IntegrityError:          # gleichzeitig von jemand anderem angelegt
            db.rollback()
            lesson = db.query(m.Lesson).filter_by(timetable_id=slot.id, date=data.date).one()

    existing = {a.student_id: a for a in db.query(m.Attendance).filter_by(lesson_id=lesson.id)}
    for e in data.entries:
        rec = existing.get(e.student_id)
        if rec is None:
            db.add(m.Attendance(student_id=e.student_id, lesson_id=lesson.id, status=e.status))
            continue
        rec.status = e.status
        if e.status == "anwesend":
            rec.excuse_id = None        # keine veraltete Entschuldigung an einer Anwesenheit
    db.commit()
    return lesson_attendance(db, cs, slot, data.date)
