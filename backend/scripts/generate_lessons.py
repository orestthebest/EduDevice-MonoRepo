"""
EduDevice - Unterrichtsstunden eines Schuljahres im Voraus anlegen (Schema V4.8)

Legt fuer jeden Unterrichtstag zwischen first_lesson_day und last_lesson_day und
jeden Stundenplan-Eintrag dieses Wochentags eine Zeile in `lessons` an.
Der Schulkalender (school_calendar) wird beachtet:
  - Feiertage, Ferien, schulautonome Tage -> keine Stunden
  - Tage mit getauschtem Stundenplan       -> Stunden des anderen Wochentags
Damit ist `lessons` der Kalender des Jahres, und die Unterrichtsminuten eines
Fachs im Jahr sind einfach die Summe seiner (nicht abgesagten) Stunden.

Sicher:
  - legt nur an, loescht und aendert NIE etwas
  - eine schon vorhandene Stunde (gleicher Stundenplan-Eintrag + Datum) wird
    uebersprungen -> kann nach jeder Stundenplan-Aenderung erneut laufen
  - --dry-run zeigt nur, was angelegt wuerde

Ausfuehren (im backend-Ordner):
  python -m scripts.generate_lessons --dry-run          # erst schauen
  python -m scripts.generate_lessons                    # dann anlegen
Optionen:
  --year 2026/27          Schuljahr (label), Standard: 2026/27
  --from 2026-11-09       erst ab diesem Datum (z. B. nach einer Stundenplan-Aenderung)
  --to 2027-04-30         nur bis zu diesem Datum
  --class 5A              nur diese Klasse (mehrfach moeglich)
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta

from app import models as m
from app.core.database import SessionLocal


def teaching_days(first: date, last: date, calendar: dict) -> list[tuple[date, str]]:
    """Alle Unterrichtstage mit dem Wochentag, dessen Stundenplan an diesem Tag gilt."""
    days = []
    d = first
    while d <= last:
        if d.weekday() < 5:
            cal = calendar.get(d)
            if cal is None:
                days.append((d, m.WEEKDAYS[d.weekday()]))
            elif cal.has_lessons:
                days.append((d, cal.timetable_weekday or m.WEEKDAYS[d.weekday()]))
        d += timedelta(days=1)
    return days


def generate(year_label: str = "2026/27", start: date | None = None, end: date | None = None,
             classes: list[str] | None = None, dry_run: bool = False) -> dict:
    db = SessionLocal()
    try:
        year = db.query(m.SchoolYear).filter_by(label=year_label).first()
        if year is None:
            raise SystemExit(f"Schuljahr '{year_label}' gibt es nicht")
        if year.first_lesson_day is None or year.last_lesson_day is None:
            raise SystemExit(f"Fuer {year_label} fehlen first_lesson_day/last_lesson_day "
                             "(zuerst kalender_2026_27.sql ausfuehren)")
        first = max(year.first_lesson_day, start or year.first_lesson_day)
        last = min(year.last_lesson_day, end or year.last_lesson_day)
        if first > last:
            raise SystemExit(f"Zeitraum leer: {first} bis {last}")

        calendar = {c.date: c for c in db.query(m.SchoolCalendarDay)
                    .filter(m.SchoolCalendarDay.date.between(first, last))}

        # Stundenplan-Eintraege dieses Schuljahres, nach Wochentag gruppiert
        query = (db.query(m.TimetableEntry, m.SchoolClass.name)
                 .join(m.ClassSubject, m.ClassSubject.id == m.TimetableEntry.class_subject_id)
                 .join(m.SchoolClass, m.SchoolClass.id == m.ClassSubject.class_id)
                 .filter(m.SchoolClass.school_year_id == year.id))
        if classes:
            query = query.filter(m.SchoolClass.name.in_(classes))
        by_weekday = defaultdict(list)
        class_of = {}
        for entry, class_name in query:
            by_weekday[entry.weekday].append(entry)
            class_of[entry.id] = class_name
        if not class_of:
            raise SystemExit("Keine Stundenplan-Eintraege gefunden - gibt es schon einen Stundenplan?")

        # schon vorhandene Stunden im Zeitraum -> werden nicht doppelt angelegt
        existing = set(db.query(m.Lesson.timetable_id, m.Lesson.date)
                       .filter(m.Lesson.timetable_id.in_(list(class_of)), m.Lesson.date.between(first, last)))

        days = teaching_days(first, last, calendar)
        created, skipped = Counter(), Counter()
        for day, weekday in days:
            for entry in by_weekday.get(weekday, []):
                if (entry.id, day) in existing:
                    skipped[class_of[entry.id]] += 1
                    continue
                created[class_of[entry.id]] += 1
                if not dry_run:
                    db.add(m.Lesson(timetable_id=entry.id, date=day, cancelled=False))

        # nur melden, nichts loeschen: vorhandene Stunden an Tagen ohne Unterricht
        no_lesson_days = [d for d, c in calendar.items() if not c.has_lessons]
        on_free_days = (db.query(m.Lesson).filter(m.Lesson.timetable_id.in_(list(class_of)),
                                                  m.Lesson.date.in_(no_lesson_days)).count()
                        if no_lesson_days else 0)

        if not dry_run:
            db.commit()

        print(f"Schuljahr {year_label}: {first} bis {last}, {len(days)} Unterrichtstage")
        for name in sorted(set(class_of.values())):
            print(f"  {name:<8} neu: {created[name]:>5}   schon vorhanden: {skipped[name]:>5}")
        print(f"  gesamt   neu: {sum(created.values()):>5}   schon vorhanden: {sum(skipped.values()):>5}")
        if on_free_days:
            print(f"  HINWEIS: {on_free_days} schon vorhandene Stunde(n) liegen an Tagen ohne Unterricht "
                  "(Feiertag/Ferien). Nichts geaendert - bitte von Hand pruefen.")
        if dry_run:
            print("  (--dry-run: nichts gespeichert)")
        return {"days": len(days), "created": dict(created), "skipped": dict(skipped),
                "on_free_days": on_free_days}
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Unterrichtsstunden eines Schuljahres im Voraus anlegen")
    p.add_argument("--year", default="2026/27")
    p.add_argument("--from", dest="start", type=date.fromisoformat)
    p.add_argument("--to", dest="end", type=date.fromisoformat)
    p.add_argument("--class", dest="classes", action="append")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    generate(a.year, a.start, a.end, a.classes, a.dry_run)


if __name__ == "__main__":
    main()
