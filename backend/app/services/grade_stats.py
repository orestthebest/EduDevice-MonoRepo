"""
grade_stats.py — die Notenarithmetik der Schule.

Reine Rechenlogik, kein Datenbankzugriff. Dadurch ist sie einzeln testbar und
wird sowohl vom Statistik-Endpunkt als auch von der Data-Science-Pipeline
verwendet.

Die Regeln stammen aus der Notenordnung der Schule und sind Vorgabe, keine
Entwurfsentscheidung:

    Notenskala      4 bis 10, wobei 10 die beste Note ist
    Gewichtung      M1 Mitarbeit 40 %, M2 Schularbeit 40 %, M3 Projekt 20 %
    Rundung         ab einem Nachkommaanteil von 0,6 wird aufgerundet
    Positiv         ab gerundeter Note 5, das entspricht einem Rohwert ab 4,6

Die Zuordnung der Kategorien zu den Komponenten folgt dem ENUM grades.category
aus dem Datenbankschema.
"""

from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import Iterable, Optional, Sequence

GRADE_MIN = Decimal("4")
GRADE_MAX = Decimal("10")

# Die Schule rundet ab 0,6 auf, nicht ab 0,5. 4,6 wird zu 5 und ist positiv,
# 4,5 bleibt 4 und ist negativ. Siehe round_grade().
ROUND_UP_AT = Decimal("0.6")
PASS_THRESHOLD = Decimal("4.6")

# Warnschwelle: positiv, aber nahe an der Grenze. Anders als PASS_THRESHOLD ist
# dies KEINE Schulregel, sondern eine Festlegung des Projekts.
FRAGILE_BELOW = Decimal("5.5")

CATEGORY_TO_COMPONENT = {
    "homework": "M1",
    "mini_test": "M1",
    "oral": "M1",
    "presentation": "M1",
    "classwork": "M1",
    "participation": "M1",
    "behaviour": "M1",
    "schularbeit": "M2",
    "project": "M3",
}

COMPONENT_WEIGHT = {
    "M1": Decimal("0.40"),
    "M2": Decimal("0.40"),
    "M3": Decimal("0.20"),
}

COMPONENT_LABEL = {
    "M1": "Mitarbeit",
    "M2": "Schularbeit",
    "M3": "Projekt",
}


class GradeError(ValueError):
    """Eine Note oder ein Gewicht verletzt die Regeln der Notenordnung."""


def _dec(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def check_grade(value, label: str = "Note") -> Decimal:
    d = _dec(value)
    if d < GRADE_MIN or d > GRADE_MAX:
        raise GradeError(f"{label}: {value} liegt ausserhalb der Skala 4..10")
    return d


def component_of(category: str) -> str:
    try:
        return CATEGORY_TO_COMPONENT[category]
    except KeyError as exc:
        raise GradeError(f"unbekannte Kategorie {category!r}") from exc


def round_grade(value) -> int:
    """Auf eine ganze Note runden - nach der Regel der Schule, ab 0,6 aufwaerts.

    Kaufmaennische Rundung waere hier falsch: Sie wuerde jeden Wert ab 4,50 zu
    einer 5 machen und damit genau den Schuelerinnen und Schuelern ein Positiv
    geben, die am knappsten an der Grenze liegen.

    Die Rechnung laeuft in Decimal, damit der Vergleich exakt ist. In
    Gleitkommazahlen ist 4.6 - 4 == 0.5999999999999996, was eine fruehere
    Fassung dieser Funktion eine 4 zurueckgeben liess.
    """
    d = _dec(value)
    whole = int(d.to_integral_value(rounding=ROUND_FLOOR))
    return whole + 1 if (d - whole) >= ROUND_UP_AT else whole


def standing(raw: Optional[Decimal]) -> str:
    """'failing' | 'fragile' | 'ok' | 'unknown' - fuer die Anzeige."""
    if raw is None:
        return "unknown"
    d = _dec(raw)
    if d < PASS_THRESHOLD:
        return "failing"
    if d < FRAGILE_BELOW:
        return "fragile"
    return "ok"


class Mark:
    """Eine Zeile der Tabelle grades, reduziert auf das, was die Rechnung braucht."""

    __slots__ = ("category", "value", "weight", "date")

    def __init__(self, category: str, value, weight=1, date=None):
        self.category = category
        self.value = check_grade(value, category)
        self.weight = _dec(weight)
        self.date = date
        if self.weight <= 0:
            raise GradeError(f"{category}: Gewicht muss positiv sein")

    @property
    def component(self) -> str:
        return component_of(self.category)


def component_grade(marks: Iterable[Mark], component: str) -> Optional[Decimal]:
    """Die Einzelnoten einer Komponente nach ihrem eigenen Gewicht zusammenfassen.

    Jede Lehrkraft legt selbst fest, woraus sich die Mitarbeitsnote ergibt,
    deshalb wird nicht nach fester Formel gerechnet, sondern mit dem jeweils
    eingetragenen Gewicht: Eine Schularbeit mit Gewicht 2 zaehlt doppelt so
    viel wie eine Hausuebung mit Gewicht 1.
    """
    selected = [m for m in marks if m.component == component]
    if not selected:
        return None
    total = sum(m.weight for m in selected)
    return sum(m.value * m.weight for m in selected) / total


def subject_grade(m1: Optional[Decimal], m2: Optional[Decimal],
                  m3: Optional[Decimal]) -> tuple[Optional[Decimal], bool, list[str]]:
    """Die drei Komponenten zur Fachnote verrechnen (40/40/20).

    Eine Komponente, die es noch nicht gibt, ist FEHLEND und nicht null. Die
    vorhandenen Gewichte werden neu normiert. Wuerde eine noch nicht
    geschriebene Schularbeit als 0 gewertet, haette im Oktober die halbe Schule
    ein Nicht genuegend - das ist der gefaehrlichste denkbare Fehler hier.

    Rueckgabe: (Rohwert, vorlaeufig, fehlende Komponenten)
    """
    parts = [("M1", m1), ("M2", m2), ("M3", m3)]
    present = [(k, v) for k, v in parts if v is not None]
    missing = [k for k, v in parts if v is None]

    if not present:
        return None, True, missing

    total_weight = sum(COMPONENT_WEIGHT[k] for k, _ in present)
    raw = sum(_dec(v) * COMPONENT_WEIGHT[k] for k, v in present) / total_weight
    return raw, bool(missing), missing


def required_remaining_avg(m1: Optional[Decimal], m2: Optional[Decimal],
                           m3: Optional[Decimal]) -> Optional[Decimal]:
    """Welchen Schnitt die noch offenen Komponenten brauchen, um positiv zu sein.

    Fuer Schuelerinnen und Schueler vermutlich die nuetzlichste Einzelzahl des
    ganzen Systems, weil sie einen Handlungsspielraum benennt statt ein Urteil.

    None, wenn nichts mehr offen ist. Ein Wert ueber 10 bedeutet, dass das Fach
    rechnerisch nicht mehr positiv abgeschlossen werden kann.
    """
    parts = [("M1", m1), ("M2", m2), ("M3", m3)]
    done = [(k, v) for k, v in parts if v is not None]
    open_ = [k for k, v in parts if v is None]
    if not open_:
        return None

    have = sum(_dec(v) * COMPONENT_WEIGHT[k] for k, v in done)
    open_weight = sum(COMPONENT_WEIGHT[k] for k in open_)
    needed = (PASS_THRESHOLD - have) / open_weight
    return needed


def mean(values: Sequence[Decimal]) -> Optional[Decimal]:
    vals = [_dec(v) for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / Decimal(len(vals))


def as_float(value: Optional[Decimal], digits: int = 2) -> Optional[float]:
    """Decimal -> float fuer die JSON-Antwort. Nur fuer den Transport runden."""
    return None if value is None else round(float(value), digits)
