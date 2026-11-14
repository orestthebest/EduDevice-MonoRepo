"""
Entwicklung der Noten in einem Fach: Rising / Steady / Falling / Up and down /
Too early. Reine Rechnung, beschreibende Statistik - deshalb live in der API
und nicht im naechtlichen Lauf.

Methode: Theil-Sen-Steigung (Median aller paarweisen Steigungen) mit einem
90-%-Vertrauensbereich nach Kendall. Robust gegen einzelne Ausreisser: eine
einzige schlechte Note macht aus "steady" noch kein "falling".

  rising / falling   der ganze Vertrauensbereich liegt ueber / unter 0 UND die
                     Veraenderung ueber den beobachteten Zeitraum ist mindestens
                     MIN_CHANGE Notenpunkte
  up_and_down        keine klare Richtung, aber die Noten streuen stark um die Linie
                     (robust gemessen: eine einzelne Ausreisser-Note reicht nicht)
  steady             sonst
  too_early          weniger als MIN_MARKS Noten an verschiedenen Tagen

Beschrieben werden die Noten, nicht der Mensch: die Seite sagt "Your marks are
rising", nie "you are declining".
"""

import math
import statistics

MIN_MARKS = 4          # darunter: too_early
MIN_CHANGE = 0.5       # Notenpunkte ueber den Zeitraum, damit eine Richtung zaehlt
SPREAD_UP_DOWN = 1.25  # Streuung um die Linie, ab der es "up and down" ist
Z90 = 1.645


def _kendall_variance(values: list[float]) -> float:
    n = len(values)
    ties = {}
    for v in values:
        ties[v] = ties.get(v, 0) + 1
    tie_term = sum(t * (t - 1) * (2 * t + 5) for t in ties.values())
    return (n * (n - 1) * (2 * n + 5) - tie_term) / 18


def growth(points: list[tuple]) -> dict:
    """points: (date, value) aller Einzelnoten eines Fachs."""
    pts = sorted((d, float(v)) for d, v in points)
    if len({d for d, _ in pts}) < MIN_MARKS:
        return {"label": "too_early", "change": None, "n": len(pts)}

    slopes = sorted((v2 - v1) / (d2 - d1).days
                    for i, (d1, v1) in enumerate(pts) for d2, v2 in pts[i + 1:] if d2 != d1)
    slope = statistics.median(slopes)
    span = (pts[-1][0] - pts[0][0]).days
    change = slope * span

    n_slopes = len(slopes)
    c = Z90 * math.sqrt(max(_kendall_variance([v for _, v in pts]), 0))
    lo_rank = max(0, int(round((n_slopes - c) / 2)) - 1)
    hi_rank = min(n_slopes - 1, int(round((n_slopes + c) / 2)))
    lower, upper = slopes[lo_rank], slopes[hi_rank]

    intercept = statistics.median(v - slope * (d - pts[0][0]).days for d, v in pts)
    residuals = [v - (intercept + slope * (d - pts[0][0]).days) for d, v in pts]
    # robuste Streuung (MAD, auf Standardabweichung skaliert): eine einzelne
    # Ausreisser-Note macht ein Fach nicht zu "up and down"
    spread = 1.4826 * statistics.median(abs(r) for r in residuals)

    if lower > 0 and change >= MIN_CHANGE:
        label = "rising"
    elif upper < 0 and change <= -MIN_CHANGE:
        label = "falling"
    elif spread >= SPREAD_UP_DOWN:
        label = "up_and_down"
    else:
        label = "steady"
    return {"label": label, "change": round(change, 2), "n": len(pts)}
