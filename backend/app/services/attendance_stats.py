"""
Fehlzeiten pro Fach (Ziel-M-3, Anwesenheit) - reine Rechnung, keine Datenbank.

Regeln der Schule (so mit Jorik festgelegt):
  - Gezaehlt werden MINUTEN, nicht Stunden: 5 Minuten zu spaet sind 5 Minuten.
  - Bezugsgroesse sind die Unterrichtsminuten des Fachs im GANZEN Jahr
    (bis zum letzten Unterrichtstag der Klasse; 5. Klassen: 30.04.).
  - Eine abgesagte Stunde zaehlt im Jahresgesamt mit, als haette sie
    stattgefunden - in ihr kann aber niemand fehlen.
  - Entschuldigt oder nicht spielt fuer die Grenzen keine Rolle.
  - Ab 20 % ist eine Pruefung noetig, ab 30 % ist das Fach nicht beurteilbar.

Die Hochrechnung ("in diesem Tempo") rechnet das bisherige Fehlen auf das
ganze Jahr hoch. Ganz am Anfang des Jahres waere sie reines Rauschen (eine
Fehlstunde in der ersten Woche ergaebe 100 %), deshalb gibt es sie erst, wenn
ein Mindestanteil des Jahres vorbei ist.
"""

EXAM_LIMIT = 0.20          # ab hier Pruefung noetig
FAIL_LIMIT = 0.30          # ab hier nicht beurteilbar
PROJECTION_FROM = 0.15     # Hochrechnung erst, wenn 15 % des Jahres vorbei sind


def absence_summary(total_minutes: int, held_minutes: int, missed_minutes: int,
                    unknown_late: int = 0, n_lessons: int = 0) -> dict | None:
    """Fehlzeiten eines Schuelers in einem Fach.

    total_minutes   Unterrichtsminuten des ganzen Jahres (abgesagte mitgezaehlt)
    held_minutes    davon bis heute (abgesagte mitgezaehlt)
    missed_minutes  versaeumte Minuten (nur in nicht abgesagten Stunden)
    unknown_late    Verspaetungen ohne erfasste Minuten (zaehlen hier als 0)
    n_lessons       Anzahl Stunden im Jahr, fuer "ungefaehr so viele Stunden"
    """
    if not total_minutes:
        return None
    rate = missed_minutes / total_minutes
    projected = None
    if held_minutes >= PROJECTION_FROM * total_minutes and held_minutes > 0:
        projected = missed_minutes / held_minutes

    if rate >= FAIL_LIMIT:
        status = "not_assessable"
    elif rate >= EXAM_LIMIT:
        status = "exam_required"
    elif projected is not None and projected >= EXAM_LIMIT:
        status = "trending"
    else:
        status = "ok"

    exam_limit = int(EXAM_LIMIT * total_minutes)
    return {
        "total_minutes": total_minutes,
        "held_minutes": held_minutes,
        "missed_minutes": missed_minutes,
        "unknown_late": unknown_late,
        "rate": round(rate, 4),
        "projected_rate": None if projected is None else round(projected, 4),
        "exam_limit_minutes": exam_limit,
        "fail_limit_minutes": int(FAIL_LIMIT * total_minutes),
        "minutes_left_before_exam": max(0, exam_limit - missed_minutes),
        "lesson_minutes": round(total_minutes / n_lessons) if n_lessons else None,
        "status": status,
    }


def overall_summary(parts: list[dict]) -> dict | None:
    """Alle Faecher zusammen: versaeumte Minuten / Jahresminuten."""
    parts = [p for p in parts if p]
    total = sum(p["total_minutes"] for p in parts)
    if not total:
        return None
    missed = sum(p["missed_minutes"] for p in parts)
    return {"total_minutes": total, "missed_minutes": missed, "rate": round(missed / total, 4)}
