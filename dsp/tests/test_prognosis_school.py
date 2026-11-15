"""Tests for prognosis_school.py - the likely final grade with its 80 % range."""

from datetime import date, timedelta
from decimal import Decimal as D

import numpy as np

import prognosis_school as ps
from scoring import DatedMark

FIRST, LAST = date(2026, 9, 3), date(2027, 6, 25)


def test_share_and_checkpoint():
    assert ps.year_share(FIRST, FIRST, LAST) == 0
    assert ps.year_share(LAST + timedelta(days=5), FIRST, LAST) == 1
    assert ps.checkpoint_for(0.23) == 0.20          # the earlier checkpoint: range a bit wider, never narrower
    assert ps.checkpoint_for(0.05) is None


def test_simulated_year_leaves_out_unfinished_students():
    rows = ps.simulated_year(ps.SEED_BASE + 1, per_class=4)
    assert rows and {r["checkpoint"] for r in rows} <= set(ps.CHECKPOINTS)
    assert all(4 <= r["final"] <= 10 and r["possible_low"] <= r["possible_high"] for r in rows)
    assert all(set(ps.FEATURES) <= r.keys() for r in rows)


def _toy_rows(n_years=3, per=60, seed=0):
    """Final = today's average + noise that shrinks over the year."""
    rng = np.random.default_rng(seed)
    rows = []
    for year in range(n_years):
        for cp in (0.2, 0.6):
            for _ in range(per):
                avg = rng.uniform(5, 9)
                row = {f: 0.0 for f in ps.FEATURES}
                row.update(average=avg, share=cp, average_x_share=avg * cp, m1=avg, m2=avg, m3=avg)
                row.update(year=year, checkpoint=cp, final=float(np.clip(avg + rng.normal(0, 1 - cp), 4, 10)))
                rows.append(row)
    return rows


def _x(average):
    return np.array([[average if f in ("average", "m1", "m2", "m3") else 0.0 for f in ps.FEATURES]])


def test_range_is_wider_early_in_the_year():
    bundle = ps.fit(_toy_rows())
    early = bundle["offsets"][(0.2, 2)][1] - bundle["offsets"][(0.2, 2)][0]    # forecasts from 7
    late = bundle["offsets"][(0.6, 2)][1] - bundle["offsets"][(0.6, 2)][0]
    assert early > late > 0
    low, point, high = ps.predict_interval(bundle, _x(7.0), [0.2])
    assert low[0] <= point[0] <= high[0]


def test_chance_to_fail_follows_the_forecast():
    bundle = ps.fit(_toy_rows())
    far_above, near, below = (ps.fail_probability(bundle, _x(v), [0.6])[0] for v in (8.5, 4.7, 4.2))
    assert far_above == 0 and below > 0.5 and 0 < near < below


def test_no_forecast_too_early_or_after_the_year():
    bundle = ps.fit(_toy_rows())
    marks = [DatedMark("mini_test", D("7"), D("1"), date(2026, 9, 20)),
             DatedMark("schularbeit", D("6"), D("2"), date(2026, 10, 1))]
    pairs, tris = {(1, 5): marks}, {5: [(FIRST, date(2026, 12, 4)), (date(2026, 12, 7), LAST)]}
    assert ps.predict_current(bundle, pairs, tris, date(2026, 10, 5)) == {}       # under 15 % of the year
    assert ps.predict_current(bundle, pairs, tris, LAST) == {}                    # year over
    [f] = ps.predict_current(bundle, pairs, tris, date(2026, 11, 15)).values()
    assert 4 <= f["low"] <= f["point"] <= f["high"] <= 10 and 0 <= f["fail_probability"] <= 1