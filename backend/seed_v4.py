"""
EduDevice - Testdaten fuer Schema V4.2
Legt Beispieldaten an, damit das Frontend (Orest) echte Antworten von der API bekommt.
Kann mehrmals ausgefuehrt werden - legt nichts doppelt an.
Ausfuehren:  python seed_v4.py

Test-Logins (NUR fuer Entwicklung) - Username oder E-Mail:
  admin     / admin@edudevice.at    / admin123
  alehrer   / lehrer@edudevice.at   / lehrer123
  tschueler / schueler@edudevice.at / schueler123
"""

from datetime import date, datetime, time, timedelta

from database import SessionLocal
from auth import hash_password
import models as m


def get_or_create(db, model, lookup: dict, extra: dict | None = None):
    obj = db.query(model).filter_by(**lookup).first()
    if obj is None:
        obj = model(**lookup, **(extra or {}))
        db.add(obj)
        db.flush()
    return obj


def seed():
    db = SessionLocal()
    try:
        admin = get_or_create(db, m.User, {"email": "admin@edudevice.at"},
                              {"first_name": "Admin", "last_name": "EduDevice", "username": "admin", "role": "admin",
                               "password_hash": hash_password("admin123")})
        lehrer = get_or_create(db, m.User, {"email": "lehrer@edudevice.at"},
                               {"first_name": "Anna", "last_name": "Lehrer", "username": "alehrer", "role": "lehrkraft",
                                "password_hash": hash_password("lehrer123")})
        schueler = get_or_create(db, m.User, {"email": "schueler@edudevice.at"},
                                 {"first_name": "Test", "last_name": "Schueler", "username": "tschueler", "role": "schueler",
                                  "password_hash": hash_password("schueler123")})

        jahr = get_or_create(db, m.SchoolYear, {"label": "2026/27"},
                             {"start_date": date(2026, 9, 1), "end_date": date(2027, 6, 30)})
        klasse = get_or_create(db, m.SchoolClass, {"school_year_id": jahr.id, "name": "4A"})
        get_or_create(db, m.StudentClass, {"student_id": schueler.id, "class_id": klasse.id})

        mathe = get_or_create(db, m.Subject, {"name": "Mathematik"})
        mathe_4a = get_or_create(db, m.ClassSubject,
                                 {"class_id": klasse.id, "subject_id": mathe.id},
                                 {"teacher_id": lehrer.id})

        stunde = get_or_create(db, m.TimetableEntry,
                               {"class_subject_id": mathe_4a.id, "weekday": "Mo",
                                "start_time": time(8, 0)},
                               {"end_time": time(8, 50), "room": "A101"})
        lesson = get_or_create(db, m.Lesson, {"timetable_id": stunde.id, "date": date(2026, 9, 28)})

        hw = get_or_create(db, m.Homework,
                           {"class_subject_id": mathe_4a.id, "description": "Buch S. 12, Aufgaben 1-5"},
                           {"due_date": datetime(2026, 10, 5, 8, 0)})

        if not db.query(m.Grade).filter_by(student_id=schueler.id).first():
            db.add(m.Grade(student_id=schueler.id, class_subject_id=mathe_4a.id,
                           category="mini_test", value=9, weight=1.0, date=date(2026, 9, 21)))

        quiz = get_or_create(db, m.Quiz, {"title": "Bruchrechnen", "class_subject_id": mathe_4a.id})

        db.commit()
        print("Testdaten bereit:")
        print(f"  admin     / admin123     (user_id={admin.id})")
        print(f"  alehrer   / lehrer123    (user_id={lehrer.id})")
        print(f"  tschueler / schueler123  (user_id={schueler.id})")
        print(f"  Klasse 4A (class_id={klasse.id}), Mathematik (subject_id={mathe.id}), "
              f"class_subject_id={mathe_4a.id}")
        print(f"  Stunde lesson_id={lesson.id} am 28.09.2026, Hausaufgabe id={hw.id}, Quiz id={quiz.id}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
