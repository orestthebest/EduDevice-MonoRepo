"""Tests Fehlzeiten (Schema V4.10, statistics V3).
Regeln: Minuten statt Stunden; Bezug = ganzes Jahr bis zum letzten Unterrichtstag
der Klasse; abgesagte Stunden zaehlen im Jahresgesamt, aber niemand fehlt darin;
Verspaetung ohne Minuten = unbekannt. Eigene Klasse und eigenes Fach, damit kein
anderer Test beeinflusst wird."""

from datetime import date, time

from app import models as m
from app.core.database import SessionLocal
from app.routers.statistics import _attendance
from app.services.attendance_stats import absence_summary

TODAY = date(2026, 11, 13)


# ---------------------------------------------------------------- reine Rechnung

def test_grenzen_und_hochrechnung():
    assert absence_summary(1000, 500, 90)["status"] == "ok"                  # 9 %, Tempo 18 %
    assert absence_summary(1000, 500, 100)["projected_rate"] == 0.2          # Tempo genau 20 % ->
    assert absence_summary(1000, 500, 100)["status"] == "trending"           # zaehlt schon
    assert absence_summary(1000, 400, 100)["status"] == "trending"           # Tempo 25 %
    assert absence_summary(1000, 900, 200)["status"] == "exam_required"      # 20 %
    assert absence_summary(1000, 900, 300)["status"] == "not_assessable"     # 30 %
    early = absence_summary(1000, 100, 50)                                   # erst 10 % des Jahres vorbei
    assert early["projected_rate"] is None and early["status"] == "ok"       # keine Hochrechnung aus Rauschen
    s = absence_summary(4350, 1450, 233, n_lessons=87)
    assert s["exam_limit_minutes"] == 870 and s["minutes_left_before_exam"] == 637
    assert s["lesson_minutes"] == 50
    assert absence_summary(0, 0, 0) is None                                  # keine Stunden angelegt


# ---------------------------------------------------------------- aus der Datenbank

def _setup():
    """Klasse '5Z' endet am 01.12. Fach mit Stunden Mo 08:00-08:50 an fuenf Montagen:
    26.10. (abwesend), 02.11. (verspaetet, 7 Min), 09.11. (abgesagt, als abwesend
    eingetragen - zaehlt nicht), 30.11. (zukuenftig), 07.12. (nach Klassenende).
    Daten so gewaehlt, dass sie sich mit keinem anderen Test ueberschneiden."""
    with SessionLocal() as db:
        existing = db.query(m.SchoolClass).filter_by(name="5Z").first()
        if existing:
            cs = db.query(m.ClassSubject).filter_by(class_id=existing.id).one()
            return cs.id
        cls = m.SchoolClass(school_year_id=1, name="5Z", last_lesson_day=date(2026, 12, 1))
        db.add(cls); db.flush()
        cs = m.ClassSubject(class_id=cls.id, subject_id=1, teacher_id=2)
        db.add(cs); db.flush()
        slot = m.TimetableEntry(class_subject_id=cs.id, weekday="Mo",
                                start_time=time(8, 0), end_time=time(8, 50))
        db.add(slot); db.flush()
        lessons = {}
        for day, cancelled in ((date(2026, 10, 26), False), (date(2026, 11, 2), False),
                               (date(2026, 11, 9), True), (date(2026, 11, 30), False),
                               (date(2026, 12, 7), False)):
            lessons[day] = m.Lesson(timetable_id=slot.id, date=day, cancelled=cancelled)
            db.add(lessons[day])
        db.flush()
        for day, status, minutes in ((date(2026, 10, 26), "abwesend", 50),
                                     (date(2026, 11, 2), "verspaetet", 7),
                                     (date(2026, 11, 9), "abwesend", 50)):
            db.add(m.Attendance(student_id=3, lesson_id=lessons[day].id, status=status,
                                minutes_missed=minutes))
        db.commit()
        return cs.id


def test_fehlzeiten_aus_stunden_und_eintraegen():
    cs_id = _setup()
    with SessionLocal() as db:
        a = _attendance(db, 3, [cs_id], TODAY)[cs_id]
    assert a["total_minutes"] == 4 * 50        # 26.10., 02.11., 09.11. (abgesagt), 30.11. - nicht 07.12.
    assert a["held_minutes"] == 3 * 50         # bis heute, abgesagte mitgezaehlt
    assert a["missed_minutes"] == 50 + 7       # die abgesagte Stunde zaehlt nicht als Fehlen
    assert a["unknown_late"] == 0


def test_verspaetung_ohne_minuten_ist_unbekannt():
    cs_id = _setup()
    with SessionLocal() as db:
        rec = (db.query(m.Attendance).join(m.Lesson, m.Lesson.id == m.Attendance.lesson_id)
               .filter(m.Attendance.student_id == 3, m.Lesson.date == date(2026, 11, 2),
                       m.Attendance.status == "verspaetet").one())
        rec.minutes_missed = None
        db.commit()
        a = _attendance(db, 3, [cs_id], TODAY)[cs_id]
        rec.minutes_missed = 7                 # zuruecksetzen fuer andere Tests
        db.commit()
    assert a["missed_minutes"] == 50 and a["unknown_late"] == 1


def test_fach_ohne_stunden_fehlt_im_ergebnis():
    with SessionLocal() as db:
        assert _attendance(db, 3, [999999], TODAY) == {}
