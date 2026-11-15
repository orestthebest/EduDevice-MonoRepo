"""
Die Jahresnote nach Trimestern - reine Rechnung, keine Datenbank.

Die API (Seite) und der naechtliche Lauf (dsp/src/score_job.py) verwenden
diese eine Datei, damit beide gleich rechnen.

So entsteht die Jahresnote
--------------------------
  M1 (Mitarbeit) und M2 (Schularbeit) werden je Trimester gemittelt, nach dem
  Gewicht der einzelnen Noten. Die Jahres-M1 ist das Mittel der Trimester-M1,
  ebenso M2 - jedes Trimester zaehlt gleich viel, egal wie viele Noten es hat.
  M3 (Projekt) gibt es einmal im Jahr. Endnote: 40 % M1, 40 % M2, 20 % M3
  (das Verrechnen und Neu-Normieren fehlender Teile macht grade_stats.py).

Was "noch offen" ist (fuer den noch moeglichen Bereich)
------------------------------------------------------
  - Trimester, die noch nicht begonnen haben: ganz offen.
  - Das laufende Trimester: die Noten, die bis zu seinem Ende noch kommen, im
    bisherigen Tempo - mindestens aber noch eine Note mit dem ueblichen
    Gewicht (kurz vor Schluss kann noch eine ganze Schularbeit kommen).
  - Ein vergangenes Trimester ist fest. Hatte es in einer Komponente keine
    Note, zaehlt es dort nicht mit.
  - Das Projekt (M3): offen, bis es benotet ist.
Alles Offene wird einmal mit lauter 4ern (schlechtester Fall) und einmal mit
lauter 10ern (bester Fall) gefuellt. "Noetiger Schnitt" ist der Schnitt, den
alles Offene braucht, damit die Endnote die Bestehensgrenze 4,6 erreicht.

Die Trimester werden als Liste (Beginn, Ende) uebergeben, schon auf den
letzten Unterrichtstag der Klasse gekuerzt (clip_to). Ohne Trimester (Tabelle
leer) zaehlt das ganze Jahr als ein Block und nur fehlende Teile sind offen.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

COMPONENT_WEIGHT = {"M1": Decimal("0.40"), "M2": Decimal("0.40"), "M3": Decimal("0.20")}
ONCE_PER_YEAR = {"M3"}                  # das Projekt: einmal im Jahr
GRADE_MIN = Decimal("4")
GRADE_MAX = Decimal("10")
PASS_THRESHOLD = Decimal("4.6")


@dataclass
class FinalRange:
    low: Decimal                        # alles Offene 4
    high: Decimal                       # alles Offene 10
    required: Decimal | None            # noetiger Schnitt auf das Offene; None = nichts mehr offen
    status: str                         # secured_pass | undecided | fail_unavoidable


def clip_to(trimesters: list[tuple[date, date]], last_day: date | None) -> list[tuple[date, date]]:
    """Die Trimester bis zum letzten Unterrichtstag der Klasse (5. Klassen: 30.04.)."""
    if last_day is None:
        return list(trimesters)
    return [(start, min(end, last_day)) for start, end in trimesters if start <= last_day]


def trimester_of(day: date | None, trimesters: list[tuple[date, date]]) -> int | None:
    """Nummer (0, 1, 2) des Trimesters einer Note. In den Ferien zwischen zwei
    Trimestern zaehlt sie zum zuletzt begonnenen, vor dem ersten zum ersten."""
    if not trimesters or day is None:
        return None
    index = 0
    for i, (start, _) in enumerate(trimesters):
        if day >= start:
            index = i
    return index


def _groups(marks, trimesters) -> dict:
    """(komponente, trimester) -> [Summe Note*Gewicht, Summe Gewicht, Anzahl].
    Das Projekt hat keinen Trimester-Schluessel (None)."""
    groups = defaultdict(lambda: [Decimal(0), Decimal(0), 0])
    for component, value, weight, day in marks:
        tri = None if component in ONCE_PER_YEAR else trimester_of(day, trimesters)
        g = groups[(component, tri)]
        g[0] += Decimal(str(value)) * Decimal(str(weight))
        g[1] += Decimal(str(weight))
        g[2] += 1
    return groups


def year_components(marks, trimesters) -> dict[str, Decimal | None]:
    """Die Jahreswerte von M1, M2, M3 nach heutigem Stand.

    marks: (komponente, note, gewicht, datum) aller bisherigen Noten eines Fachs.
    M1/M2: Mittel der Trimester, in denen es schon Noten gibt. None = noch keine Note.
    """
    groups = _groups(marks, trimesters)
    out = {}
    for k in COMPONENT_WEIGHT:
        means = [s / w for (c, _), (s, w, _) in groups.items() if c == k]
        out[k] = sum(means) / len(means) if means else None
    return out


def final_range(marks, trimesters, today: date) -> FinalRange:
    """Noch moeglicher Bereich der Endnote.

    Jede Komponente ist  fest + offen * x  (x = Schnitt auf alles Offene);
    die Endnote ist die Summe mit 40/40/20.
    """
    groups = _groups(marks, trimesters)
    fixed, open_ = Decimal(0), Decimal(0)

    for k, w in COMPONENT_WEIGHT.items():
        if k in ONCE_PER_YEAR or not trimesters:
            # ein Block fuer das ganze Jahr: fest, sobald es eine Note gibt
            g = groups.get((k, None))
            if g:
                fixed += w * g[0] / g[1]
            else:
                open_ += w
            continue

        parts = []                                  # je zaehlendem Trimester: (Schnitt, offener Anteil)
        for i, (start, end) in enumerate(trimesters):
            g = groups.get((k, i))
            if today > end:                         # vorbei
                if g:
                    parts.append((g[0] / g[1], Decimal(0)))
                continue                            # vorbei ohne Note: zaehlt nicht mit
            if today < start or not g:              # kommt noch / laeuft, aber noch ohne Note
                parts.append((None, Decimal(1)))
                continue
            # laeuft: bisheriges Tempo bis Trimesterende, mindestens noch eine Note
            have, count = g[1], g[2]
            remaining = (end - today).days
            if remaining <= 0:
                coming = Decimal(0)
            else:
                elapsed = max((today - start).days, 1)
                coming = max(have * remaining / elapsed, have / count)
            parts.append((g[0] / g[1], coming / (have + coming)))

        if not parts:                               # Jahr vorbei, nie eine Note
            open_ += w
            continue
        n = len(parts)
        for mean, share_open in parts:
            if mean is not None:
                fixed += w * mean * (1 - share_open) / n
            open_ += w * share_open / n

    low = fixed + open_ * GRADE_MIN
    high = fixed + open_ * GRADE_MAX
    required = None if open_ == 0 else (PASS_THRESHOLD - fixed) / open_

    if low >= PASS_THRESHOLD:
        status = "secured_pass"
    elif high < PASS_THRESHOLD:
        status = "fail_unavoidable"
    else:
        status = "undecided"
    return FinalRange(low, high, required, status)