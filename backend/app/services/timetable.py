"""Stundenplan-Logik (V4.11): Gueltigkeit, Stundenraster, Unterrichtsstunden anlegen/loeschen, Konflikte.

Ein Stundenplan-Eintrag (Tabelle timetable) gilt an einem Datum, wenn
valid_from <= Datum und (valid_to IS NULL oder valid_to >= Datum).
Aendern = alten Eintrag beenden + neuen anlegen, damit die Geschichte (Anwesenheiten) bleibt.
"""

from datetime import date, time, timedelta
from typing import Optional

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import PERIODS

TE = m.TimetableEntry


# ---------------- Gueltigkeit und Raster ----------------
def valid_on(day):
    """SQL-Bedingung: Eintrag gilt an diesem Tag (day darf auch eine Spalte sein, z. B. Lesson.date)."""
    return and_(TE.valid_from <= day, or_(TE.valid_to.is_(None), TE.valid_to >= day))


def active_from(day: date):
    """SQL-Bedingung: Eintrag gilt an diesem Tag oder spaeter noch (fuer Konflikte bei neuen Eintraegen)."""
    return or_(TE.valid_to.is_(None), TE.valid_to >= day)


def period_of(start: time) -> Optional[int]:
    """Periode zur Beginnzeit, None wenn die Zeit nicht ins Raster passt (alte Eintraege)."""
    for p, (s, _) in PERIODS.items():
        if s == start:
            return p
    return None


def overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


# ---------------- Unterrichtsstunden (lessons) ----------------
def school_days(db: Session, first: date, last: date) -> list[tuple[date, str]]:
    """(Datum, Wochentag des geltenden Stundenplans) fuer jeden Unterrichtstag zwischen first und last.
    Beachtet den Schulkalender: freie Tage fallen weg, getauschte Tage bekommen den anderen Wochentag."""
    calendar = {c.date: c for c in db.query(m.SchoolCalendarDay)
                .filter(m.SchoolCalendarDay.date.between(first, last))}
    days, d = [], first
    while d <= last:
        if d.weekday() < 5:
            cal = calendar.get(d)
            if cal is None:
                days.append((d, m.WEEKDAYS[d.weekday()]))
            elif cal.has_lessons:
                days.append((d, cal.timetable_weekday or m.WEEKDAYS[d.weekday()]))
        d += timedelta(days=1)
    return days


def last_day_for(db: Session, cs: m.ClassSubject) -> Optional[date]:
    """Letzter Unterrichtstag der Klasse (V4.10) oder des Schuljahres."""
    klasse = db.get(m.SchoolClass, cs.class_id)
    year = db.get(m.SchoolYear, klasse.school_year_id)
    return klasse.last_lesson_day or year.last_lesson_day or year.end_date


def create_lessons(db: Session, entries: list[m.TimetableEntry], first: date, last: Optional[date]) -> int:
    """Legt fuer die Eintraege alle Stunden von first bis last an (vorhandene werden uebersprungen)."""
    if not entries or last is None or first > last:
        return 0
    ids = [e.id for e in entries]
    existing = set(db.query(m.Lesson.timetable_id, m.Lesson.date)
                   .filter(m.Lesson.timetable_id.in_(ids), m.Lesson.date.between(first, last)))
    created = 0
    for day, weekday in school_days(db, first, last):
        for e in entries:
            if e.weekday != weekday or (e.id, day) in existing:
                continue
            if day < e.valid_from or (e.valid_to is not None and day > e.valid_to):
                continue
            db.add(m.Lesson(timetable_id=e.id, date=day, cancelled=False))
            created += 1
    return created


def delete_lessons_without_attendance(db: Session, entry_id: int, from_day: date) -> int:
    """Loescht Stunden dieses Eintrags ab from_day, fuer die noch keine Anwesenheit erfasst ist."""
    has_att = exists().where(m.Attendance.lesson_id == m.Lesson.id)
    lessons = (db.query(m.Lesson)
               .filter(m.Lesson.timetable_id == entry_id, m.Lesson.date >= from_day, ~has_att).all())
    for lesson in lessons:
        db.delete(lesson)
    return len(lessons)


def has_attendance(db: Session, entry_id: int) -> bool:
    return db.query(exists().where(m.Attendance.lesson_id == m.Lesson.id)
                    .where(m.Lesson.timetable_id == entry_id)).scalar()


# ---------------- Konflikte ----------------
def find_conflict(db: Session, cs: m.ClassSubject, weekday: str, periods: list[int],
                  room: Optional[str], today: date) -> Optional[str]:
    """Erster Konflikt als englischer Satz fuer den Admin (Orest zeigt ihn 1:1 an), sonst None.
    Geprueft wird ueber ueberlappende Uhrzeiten, damit auch alte Eintraege ausserhalb des Rasters zaehlen.
    Parallele Faecher derselben Klasse (Gruppen) sind erlaubt, solange sich weder Lehrkraft,
    Raum noch SchuelerInnen ueberschneiden."""
    rows = (db.query(TE, m.ClassSubject, m.SchoolClass.name, m.Subject.name, m.User.username)
            .join(m.ClassSubject, m.ClassSubject.id == TE.class_subject_id)
            .join(m.SchoolClass, m.SchoolClass.id == m.ClassSubject.class_id)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .join(m.User, m.User.id == m.ClassSubject.teacher_id)
            .filter(TE.weekday == weekday, active_from(today)).all())
    if not rows:
        return None

    def students_of(cs_id: int) -> set[int]:
        return {r[0] for r in db.query(m.ClassSubjectStudent.student_id).filter_by(class_subject_id=cs_id)}

    mine = students_of(cs.id)
    enrolled_cache: dict[int, set[int]] = {}
    room_key = room.lower() if room else None

    for p in periods:
        start, end = PERIODS[p]
        for entry, other_cs, class_name, subject_name, teacher in rows:
            if not overlaps(start, end, entry.start_time, entry.end_time):
                continue
            if other_cs.id == cs.id:
                return f"{subject_name} for class {class_name} already has a lesson on {weekday} in period {p}"
            if other_cs.teacher_id == cs.teacher_id:
                return f"{teacher} already teaches class {class_name} in period {p}"
            if room_key and entry.room and entry.room.lower() == room_key:
                return f"Room {entry.room} is already used by class {class_name} in period {p}"
            if other_cs.id not in enrolled_cache:
                enrolled_cache[other_cs.id] = students_of(other_cs.id)
            both = mine & enrolled_cache[other_cs.id]
            if both:
                s = (db.query(m.User).filter(m.User.id.in_(both))
                     .order_by(m.User.last_name, m.User.first_name).first())
                return f"{s.first_name} {s.last_name} is already in {subject_name} in period {p}"
    return None
