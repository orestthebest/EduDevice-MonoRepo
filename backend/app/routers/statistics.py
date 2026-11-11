"""
Notenstatistiken (Ziel-M-3): GET /statistics/student/{student_id}

Liefert die fertig gerechnete Notenuebersicht einer Schuelerin oder eines
Schuelers. Die Rechenregeln stehen in services/grade_stats.py.

Warum ein eigener Endpunkt und nicht die Rechnung im Frontend?
  - Die Notenordnung ist Fachlogik und darf nur an einer Stelle stehen. Zwei
    Implementierungen (hier und im Frontend) wuerden frueher oder spaeter
    unterschiedliche Noten anzeigen.
  - Dieselbe Antwort wird spaeter auch vom EduDevice abgerufen. Das Geraet
    rechnet nicht selbst, es stellt nur dar.

Zugriffsregeln (dieselben wie in grades.py):
  schueler    nur die eigenen Daten
  lehrkraft   nur Faecher, die sie selbst unterrichtet
  admin       alles

Der Klassenvergleich wird ausschliesslich aggregiert ausgeliefert - Mittelwert
und eigene Position. Namen oder Noten einzelner Mitschuelerinnen und
Mitschueler verlassen diesen Endpunkt nie.

V2 (November 2026):
  recent_overall  die neuesten Noten ueber alle Faecher, je mit ihrer Wirkung
                  auf den Fachschnitt
  progression     Verlauf des Fachschnitts nach jedem Notentag (fuer die Verlaufslinie)
  notices         Hinweise, die oben auf der Seite stehen (nicht mehr erreichbar,
                  unter der Grenze, knapp darueber) - als Daten, der Text steht
                  im Frontend; spaeter kommen hier Anwesenheitshinweise dazu
  insights        die Beobachtungen der Woche aus student_insights (geschrieben
                  vom naechtlichen Auswertungslauf)
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models as m
from app.core.database import get_db
from app.core.security import get_current_user, role_of
from app.services import grade_stats as gs

router = APIRouter(prefix="/statistics", tags=["Notenstatistiken"])


def _trimester_windows(db: Session) -> list[dict]:
    """Die Trimesterzeitraeume aus der Tabelle trimesters.

    Die Tabelle gehoert zum Schema, hat in models.py aber noch kein ORM-Modell,
    deshalb hier als einfache Abfrage. Ist sie leer, liefert die Funktion eine
    leere Liste und die Auswertung laesst die Trimesteraufteilung weg, statt
    falsche Zahlen zu zeigen.
    """
    try:
        rows = db.execute(text(
            "SELECT number, start_date, end_date FROM trimesters ORDER BY number"
        )).all()
    except Exception:
        return []
    return [{"number": r[0], "start": r[1], "end": r[2]} for r in rows]


def _trimester_of(day: date, windows: list[dict]):
    for w in windows:
        if w["start"] <= day <= w["end"]:
            return w["number"]
    return None


RECENT_OVERALL = 6          # so viele neueste Noten im Kasten "Recent grades"
NEW_DAYS = 7                # Noten der letzten 7 Tage bekommen die Markierung "new"
INSIGHTS_SHOWN = 3          # so viele Beobachtungen pro Woche
INSIGHTS_MAX_AGE_DAYS = 13  # aeltere Wochen werden nicht mehr gezeigt (Lauf ausgefallen)


def _raw_grade(marks: list) -> Decimal | None:
    """Fachschnitt (ungerundet) aus Einzelnoten - dieselbe Rechnung wie ueberall."""
    raw, _, _ = gs.subject_grade(gs.component_grade(marks, "M1"),
                                 gs.component_grade(marks, "M2"),
                                 gs.component_grade(marks, "M3"))
    return raw


def _progression(rows) -> list[dict]:
    """Fachschnitt nach jedem Notentag: so hat sich der Schnitt im Jahr entwickelt.
    Mehrere Noten am selben Tag ergeben einen Punkt."""
    points, seen = [], []
    by_date = defaultdict(list)
    for r in rows:
        by_date[r.date].append(r)
    for day in sorted(by_date):
        seen += [gs.Mark(r.category, r.value, r.weight, r.date) for r in by_date[day]]
        raw = _raw_grade(seen)
        if raw is not None:
            points.append({"date": day.isoformat(), "raw": gs.as_float(raw)})
    return points


def _recent_overall(grades, meta: dict, today: date) -> list[dict]:
    """Die neuesten Noten ueber alle Faecher.

    effect = Fachschnitt mit dieser Note minus Fachschnitt ohne sie. Fuer die
    neueste Note eines Fachs ist das genau "vorher -> nachher". Eine 6 bedeutet
    etwas anderes, wenn sie den Schnitt hebt, als wenn sie ihn senkt.
    """
    by_subject = defaultdict(list)
    for g in grades:
        by_subject[g.class_subject_id].append(g)

    newest = sorted(grades, key=lambda g: (g.date, g.id), reverse=True)[:RECENT_OVERALL]
    out = []
    for g in newest:
        rows = by_subject[g.class_subject_id]
        with_it = _raw_grade([gs.Mark(r.category, r.value, r.weight, r.date) for r in rows])
        without = _raw_grade([gs.Mark(r.category, r.value, r.weight, r.date)
                              for r in rows if r.id != g.id])
        effect = None if with_it is None or without is None else gs.as_float(with_it - without)
        out.append({
            "class_subject_id": g.class_subject_id,
            "subject_name": meta.get(g.class_subject_id, {}).get("subject_name", ""),
            "category": g.category,
            "component": gs.component_of(g.category),
            "value": float(g.value),
            "weight": float(g.weight),
            "date": g.date.isoformat(),
            "is_new": (today - g.date).days < NEW_DAYS,
            "effect": effect,
        })
    return out


def _notices(subjects: list[dict]) -> list[dict]:
    """Was oben auf der Seite stehen soll, wichtigstes zuerst.
    Nur Daten (Art + Zahlen); die Saetze stehen im Frontend."""
    order = {"unreachable": 0, "failing": 1, "fragile": 2}
    out = []
    for s in subjects:
        if not s["reachable"]:
            kind = "unreachable"
        elif s["standing"] in ("failing", "fragile"):
            kind = s["standing"]
        else:
            continue
        out.append({
            "kind": kind,
            "class_subject_id": s["class_subject_id"],
            "subject_name": s["subject_name"],
            "current": s["current"]["raw"],
            "required_remaining_avg": s["required_remaining_avg"],
            "secured": s["secured"],
        })
    out.sort(key=lambda n: (order[n["kind"]], n["current"] if n["current"] is not None else 0))
    return out


def _insights(db: Session, student_id: int, visible_cs: set[int] | None, today: date) -> list[dict]:
    """Die Beobachtungen der Woche (Tabelle student_insights, Schema V4.8).

    Geschrieben werden sie vom naechtlichen Auswertungslauf; gezeigt werden die
    staerksten des letzten Laufs. Die Tabelle hat (noch) kein ORM-Modell, daher
    eine direkte Abfrage. Fehlt sie oder ist sie leer, kommt eine leere Liste -
    die Seite zeigt dann ihren Platzhalter.
    visible_cs: fuer Lehrkraefte nur Beobachtungen zu eigenen Faechern (None = alle).

    Regel fuer den Auswertungslauf: message enthaelt den Fachnamen NICHT -
    die Seite stellt ihn selbst voran ("Mathematics: ..."). Saetze auf Englisch.
    """
    try:
        rows = db.execute(text("""
            SELECT i.kind, i.tone, i.message, i.class_subject_id, s.name, i.week_start
            FROM student_insights i
            LEFT JOIN class_subjects cs ON cs.id = i.class_subject_id
            LEFT JOIN subjects s ON s.id = cs.subject_id
            WHERE i.student_id = :sid
              AND i.run_id = (SELECT MAX(run_id) FROM student_insights WHERE student_id = :sid)
            ORDER BY i.score DESC
        """), {"sid": student_id}).all()
    except Exception:
        return []
    out = []
    for kind, tone, message, cs_id, subject_name, week_start in rows:
        if (today - week_start).days > INSIGHTS_MAX_AGE_DAYS:
            return []
        if visible_cs is not None and cs_id not in visible_cs:
            continue
        out.append({"kind": kind, "tone": tone, "message": message,
                    "class_subject_id": cs_id, "subject_name": subject_name,
                    "week_start": week_start.isoformat()})
        if len(out) == INSIGHTS_SHOWN:
            break
    return out


def _subject_names(db: Session, cs_ids: list[int]) -> dict[int, dict]:
    """class_subject_id -> Fachname, Klassenname, Lehrkraft."""
    if not cs_ids:
        return {}
    rows = (db.query(m.ClassSubject.id, m.Subject.name, m.SchoolClass.name,
                     m.ClassSubject.teacher_id)
            .join(m.Subject, m.Subject.id == m.ClassSubject.subject_id)
            .join(m.SchoolClass, m.SchoolClass.id == m.ClassSubject.class_id)
            .filter(m.ClassSubject.id.in_(cs_ids))
            .all())
    return {r[0]: {"subject_name": r[1], "class_name": r[2], "teacher_id": r[3]}
            for r in rows}


def _class_average(db: Session, cs_id: int, exclude_student: int):
    """Mittelwert der Fachnoten aller uebrigen Lernenden - nur als Aggregat.

    Rueckgabe (Mittelwert, Anzahl) oder (None, 0), wenn zu wenige Daten
    vorliegen. Unter drei Vergleichspersonen wird nichts ausgeliefert, weil
    sich aus einem Mittelwert ueber ein oder zwei Personen die Einzelnote
    zurueckrechnen liesse.
    """
    rows = db.query(m.Grade).filter(m.Grade.class_subject_id == cs_id,
                                    m.Grade.student_id != exclude_student).all()
    by_student = defaultdict(list)
    for r in rows:
        by_student[r.student_id].append(
            gs.Mark(r.category, r.value, r.weight, r.date))

    finals = []
    for marks in by_student.values():
        raw, _, _ = gs.subject_grade(gs.component_grade(marks, "M1"),
                                     gs.component_grade(marks, "M2"),
                                     gs.component_grade(marks, "M3"))
        if raw is not None:
            finals.append(raw)

    if len(finals) < 3:
        return None, len(finals)
    return gs.mean(finals), len(finals)


@router.get("/student/{student_id}")
def student_statistics(student_id: int, db: Session = Depends(get_db),
                       current: m.User = Depends(get_current_user)):
    role = role_of(current)
    if role == "schueler" and current.id != student_id:
        raise HTTPException(status_code=403, detail="Nur eigene Statistiken einsehbar")

    student = db.get(m.User, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Schueler nicht gefunden")

    query = db.query(m.Grade).filter(m.Grade.student_id == student_id)
    if role == "lehrkraft":
        query = (query.join(m.ClassSubject, m.Grade.class_subject_id == m.ClassSubject.id)
                      .filter(m.ClassSubject.teacher_id == current.id))
    grades = query.order_by(m.Grade.date).all()

    windows = _trimester_windows(db)
    meta = _subject_names(db, sorted({g.class_subject_id for g in grades}))

    by_subject = defaultdict(list)
    for g in grades:
        by_subject[g.class_subject_id].append(g)

    subjects = []
    for cs_id, rows in by_subject.items():
        marks = [gs.Mark(r.category, r.value, r.weight, r.date) for r in rows]
        m1 = gs.component_grade(marks, "M1")
        m2 = gs.component_grade(marks, "M2")
        m3 = gs.component_grade(marks, "M3")
        raw, provisional, missing = gs.subject_grade(m1, m2, m3)

        # Komponenten einzeln, mit Anzahl der eingegangenen Einzelnoten
        components = []
        for key, value in (("M1", m1), ("M2", m2), ("M3", m3)):
            n = sum(1 for mk in marks if mk.component == key)
            components.append({
                "key": key,
                "label": gs.COMPONENT_LABEL[key],
                "weight": float(gs.COMPONENT_WEIGHT[key]),
                "raw": gs.as_float(value),
                "rounded": None if value is None else gs.round_grade(value),
                "n_marks": n,
            })

        # Entwicklung ueber die Trimester (nur M1 und M2 - M3 zaehlt fuers Jahr)
        by_trimester = []
        if windows:
            for w in windows:
                tri_marks = [mk for mk in marks
                             if mk.date and _trimester_of(mk.date, windows) == w["number"]]
                if not tri_marks:
                    by_trimester.append({"trimester": w["number"], "raw": None,
                                         "rounded": None, "n_marks": 0})
                    continue
                t1 = gs.component_grade(tri_marks, "M1")
                t2 = gs.component_grade(tri_marks, "M2")
                t_raw, _, _ = gs.subject_grade(t1, t2, None)
                by_trimester.append({
                    "trimester": w["number"],
                    "raw": gs.as_float(t_raw),
                    "rounded": None if t_raw is None else gs.round_grade(t_raw),
                    "n_marks": len(tri_marks),
                })

        class_mean, n_compared = _class_average(db, cs_id, student_id)
        comparison = None
        if class_mean is not None and raw is not None:
            comparison = {
                "class_mean": gs.as_float(class_mean),
                "delta": gs.as_float(raw - class_mean),
                "n_compared": n_compared,
            }

        needed = gs.required_remaining_avg(m1, m2, m3)
        info = meta.get(cs_id, {})
        subjects.append({
            "class_subject_id": cs_id,
            "subject_name": info.get("subject_name", f"Fach {cs_id}"),
            "class_name": info.get("class_name", ""),
            "current": {
                "raw": gs.as_float(raw),
                "rounded": None if raw is None else gs.round_grade(raw),
                "provisional": provisional,
                "missing": missing,
            },
            "standing": gs.standing(raw),
            "components": components,
            "by_trimester": by_trimester,
            "required_remaining_avg": gs.as_float(needed),
            "reachable": needed is None or needed <= gs.GRADE_MAX,
            # schon sicher bestanden: selbst lauter 4er auf das Offene reichen
            # (dann ist der "noetige Schnitt" kleiner als die kleinste Note)
            "secured": needed is not None and needed <= gs.GRADE_MIN,
            "class_comparison": comparison,
            "n_marks": len(marks),
            "progression": _progression(rows),
            "recent": [
                {"category": r.category, "value": float(r.value),
                 "weight": float(r.weight), "date": r.date.isoformat(),
                 "component": gs.component_of(r.category)}
                for r in sorted(rows, key=lambda r: r.date, reverse=True)[:5]
            ],
        })

    subjects.sort(key=lambda s: (s["current"]["raw"] is None,
                                 s["current"]["raw"] if s["current"]["raw"] is not None else 0))

    finals = [Decimal(str(s["current"]["raw"])) for s in subjects
              if s["current"]["raw"] is not None]
    overall = gs.mean(finals)
    today = date.today()

    return {
        "student": {"id": student.id,
                    "name": f"{student.first_name} {student.last_name}"},
        "as_of": today.isoformat(),
        "scale": {"min": 4, "max": 10, "best": 10,
                  "pass_threshold": float(gs.PASS_THRESHOLD),
                  "fragile_below": float(gs.FRAGILE_BELOW)},
        "has_trimesters": bool(windows),
        "overall": {
            "raw": gs.as_float(overall),
            "rounded": None if overall is None else gs.round_grade(overall),
            "n_subjects": len(subjects),
            "n_at_risk": sum(1 for s in subjects if s["standing"] == "failing"),
            "n_fragile": sum(1 for s in subjects if s["standing"] == "fragile"),
            "n_ok": sum(1 for s in subjects if s["standing"] == "ok"),
        },
        "notices": _notices(subjects),
        "recent_overall": _recent_overall(grades, meta, today),
        "insights": _insights(db, student_id,
                              set(meta) if role == "lehrkraft" else None, today),
        "subjects": subjects,
    }
