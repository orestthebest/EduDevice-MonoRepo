"""Stundenplan.
Ziel-M-4:  GET /timetable/{user_id}                (nur gerade gueltige Eintraege)
V4.11:     GET /timetable/periods                  Stundenraster
           GET /timetable/week?user_id=&date=      Stunden einer Woche + Schulkalender
           GET /timetable/class/{class_id}         Stundenplan einer Klasse (admin)
           POST /timetable                         Block anlegen (admin)
           DELETE /timetable/{id}                  Eintrag entfernen (admin)
Aendern macht die WebApp als DELETE + POST. Siehe services/timetable.py fuer die Regeln.
"""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import PERIODS
from app.core.database import get_db
from app.core.security import get_current_user, require_roles, role_of
from app.schemas import (CalendarDayOut, PeriodOut, TimetableCreateIn, TimetableOut, TimetableRowOut,
                         WeekLessonOut, WeekOut)
from app.services import timetable as tt
from app.services.access import student_class_ids

router = APIRouter(prefix="/timetable", tags=["Stundenplan"])
WEEKDAY_ORDER = {d: i for i, d in enumerate(m.WEEKDAYS)}
TE = m.TimetableEntry


def hhmm(t) -> str:
    return t.strftime("%H:%M")


def user_or_403_404(db: Session, user_id: int, current: m.User) -> m.User:
    if role_of(current) != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Nur eigener Stundenplan einsehbar")
    target = db.get(m.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return target


def rows_out(db: Session, entries_query) -> list[TimetableRowOut]:
    rows = (entries_query
            .join(m.ClassSubject, m.ClassSubject.id == TE.class_subject_id)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .join(m.User, m.User.id == m.ClassSubject.teacher_id)
            .add_columns(m.Subject.name, m.User.last_name, m.User.username).all())
    rows.sort(key=lambda r: (WEEKDAY_ORDER.get(r[0].weekday, 9), r[0].start_time, r[1]))
    return [TimetableRowOut(id=e.id, class_subject_id=e.class_subject_id, weekday=e.weekday,
                            period=tt.period_of(e.start_time), start_time=hhmm(e.start_time),
                            end_time=hhmm(e.end_time), room=e.room, subject=subject,
                            teacher=last_name, teacher_username=username)
            for e, subject, last_name, username in rows]


# ---------------- Raster ----------------
@router.get("/periods", response_model=list[PeriodOut])
def periods(current: m.User = Depends(get_current_user)):
    return [PeriodOut(period=p, start=hhmm(s), end=hhmm(e)) for p, (s, e) in PERIODS.items()]


# ---------------- Wochenansicht ----------------
@router.get("/week", response_model=WeekOut)
def week(user_id: int, date: date, db: Session = Depends(get_db),
         current: m.User = Depends(get_current_user)):
    """Alle Stunden der Woche (Mo-Fr) und alle Eintraege im Schulkalender dieser Woche.
    SchuelerIn: Faecher, in denen sie eingetragen ist (Gruppen!). Lehrkraft: eigene Faecher.
    date darf jeder Tag der Woche sein, es wird auf den Montag gerechnet."""
    target = user_or_403_404(db, user_id, current)
    monday = date - timedelta(days=date.weekday())
    friday = monday + timedelta(days=4)

    q = (db.query(m.Lesson, TE, m.ClassSubject, m.Subject.name, m.SchoolClass.name,
                  m.User.last_name, m.User.username)
         .join(TE, TE.id == m.Lesson.timetable_id)
         .join(m.ClassSubject, m.ClassSubject.id == TE.class_subject_id)
         .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
         .join(m.SchoolClass, m.SchoolClass.id == m.ClassSubject.class_id)
         .join(m.User, m.User.id == m.ClassSubject.teacher_id)
         .filter(m.Lesson.date.between(monday, friday), tt.valid_on(m.Lesson.date)))
    role = role_of(target)
    if role == "schueler":
        q = q.join(m.ClassSubjectStudent, (m.ClassSubjectStudent.class_subject_id == m.ClassSubject.id)
                   & (m.ClassSubjectStudent.student_id == target.id))
    elif role == "lehrkraft":
        q = q.filter(m.ClassSubject.teacher_id == target.id)
    else:
        q = q.filter(False)          # Admin hat keinen eigenen Unterricht

    lessons = [WeekLessonOut(lesson_id=l.id, date=l.date, period=tt.period_of(e.start_time),
                             start_time=hhmm(e.start_time), end_time=hhmm(e.end_time),
                             class_subject_id=cs.id, subject=subject, class_name=class_name,
                             teacher=last_name, teacher_username=username, room=e.room,
                             cancelled=bool(l.cancelled))
               for l, e, cs, subject, class_name, last_name, username in q.all()]
    lessons.sort(key=lambda x: (x.date, x.start_time, x.subject))

    calendar = [CalendarDayOut(date=c.date, day_type=c.day_type, has_lessons=c.has_lessons,
                               timetable_weekday=c.timetable_weekday, note=c.note)
                for c in db.query(m.SchoolCalendarDay)
                .filter(m.SchoolCalendarDay.date.between(monday, friday))
                .order_by(m.SchoolCalendarDay.date)]
    return WeekOut(week_start=monday, lessons=lessons, calendar=calendar)


# ---------------- Admin: Stundenplan einer Klasse ----------------
@router.get("/class/{class_id}", response_model=list[TimetableRowOut])
def class_timetable(class_id: int, db: Session = Depends(get_db),
                    current: m.User = Depends(require_roles("admin"))):
    """Die heute gueltigen Eintraege aller Faecher dieser Klasse."""
    if db.get(m.SchoolClass, class_id) is None:
        raise HTTPException(status_code=404, detail="Class not found")
    ids = [r[0] for r in db.query(TE.id).join(m.ClassSubject, m.ClassSubject.id == TE.class_subject_id)
           .filter(m.ClassSubject.class_id == class_id, tt.valid_on(date.today()))]
    return rows_out(db, db.query(TE).filter(TE.id.in_(ids)))


@router.post("", response_model=list[TimetableRowOut], status_code=201)
def create_block(data: TimetableCreateIn, db: Session = Depends(get_db),
                 current: m.User = Depends(require_roles("admin"))):
    """Block anlegen (eine Zeile pro Periode), gueltig ab heute. 409 bei Konflikt, der Text ist englisch,
    weil die WebApp ihn 1:1 anzeigt. Danach werden die Stunden bis Schuljahresende angelegt."""
    cs = db.get(m.ClassSubject, data.class_subject_id)
    if cs is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    today = date.today()
    room = (data.room or "").strip() or None
    periods_ = list(range(data.period_from, data.period_to + 1))

    conflict = tt.find_conflict(db, cs, data.weekday, periods_, room, today)
    if conflict:
        raise HTTPException(status_code=409, detail=conflict)

    entries = []
    for p in periods_:
        start, end = PERIODS[p]
        e = TE(class_subject_id=cs.id, weekday=data.weekday, start_time=start, end_time=end,
               room=room, valid_from=today, valid_to=None)
        db.add(e)
        entries.append(e)
    db.flush()                                            # IDs fuer die Stunden
    tt.create_lessons(db, entries, today, tt.last_day_for(db, cs))
    db.commit()
    ids = [e.id for e in entries]
    return rows_out(db, db.query(TE).filter(TE.id.in_(ids)))


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db),
                 current: m.User = Depends(require_roles("admin"))):
    """Mit Anwesenheiten: Eintrag endet gestern (Geschichte bleibt). Ohne: wirklich loeschen.
    In beiden Faellen verschwinden kuenftige Stunden ohne Anwesenheit."""
    e = db.get(TE, entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Timetable entry not found")
    today = date.today()
    if tt.has_attendance(db, e.id):
        tt.delete_lessons_without_attendance(db, e.id, today)
        if e.valid_to is None or e.valid_to >= today:
            e.valid_to = today - timedelta(days=1)
    else:
        # keine Anwesenheiten -> alle Stunden dieses Eintrags koennen weg, dann der Eintrag selbst
        db.query(m.Lesson).filter(m.Lesson.timetable_id == entry_id).delete(synchronize_session=False)
        db.delete(e)
    db.commit()
    return Response(status_code=204)


# ---------------- Ziel-M-4: Stundenplan einer Person ----------------
@router.get("/{user_id}", response_model=list[TimetableOut])
def get_timetable(user_id: int, db: Session = Depends(get_db), current: m.User = Depends(get_current_user)):
    """Heute gueltige Eintraege. SchuelerIn: Faecher ihrer Klasse, Lehrkraft: eigene Faecher."""
    target = user_or_403_404(db, user_id, current)
    query = (db.query(TE, m.Subject.name, m.SchoolClass.name)
             .join(m.ClassSubject, TE.class_subject_id == m.ClassSubject.id)
             .join(m.Subject, m.ClassSubject.subject_id == m.Subject.id)
             .join(m.SchoolClass, m.ClassSubject.class_id == m.SchoolClass.id)
             .filter(tt.valid_on(date.today())))
    role = role_of(target)
    if role == "schueler":
        query = query.filter(m.ClassSubject.class_id.in_(student_class_ids(db, user_id)))
    elif role == "lehrkraft":
        query = query.filter(m.ClassSubject.teacher_id == user_id)
    else:
        return []
    rows = sorted(query.all(), key=lambda r: (WEEKDAY_ORDER.get(r[0].weekday, 9), r[0].start_time))
    return [TimetableOut(id=t.id, class_subject_id=t.class_subject_id, subject=subject, class_name=cls,
                         weekday=t.weekday, start_time=hhmm(t.start_time), end_time=hhmm(t.end_time),
                         room=t.room, period=tt.period_of(t.start_time))
            for t, subject, cls in rows]
