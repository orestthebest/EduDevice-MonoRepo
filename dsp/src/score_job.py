"""
score_job.py — the nightly scoring job (runs from cron, or by hand).

What one run does
-----------------
For every student in every subject of the school year:

  risk_assessments   status (secured / undecided / cannot pass), the possible
                     range of the final grade, the needed average, the absence
                     rate, and the chance to fail from the prognosis model
                     (NULL when the rules already decide the outcome)
  grade_forecasts    the likely final grade with its 80 % range (prognosis_school
                     model), clipped into the possible range; from 15 % of the year
  alerts             for teachers: fail risk, attendance 20 % / 30 % / trend,
                     unusual drop - each only once, not again every night
  student_insights   the week's observations for the student page (top 3)
  pipeline_runs      one row per run: running -> success / failed (+ error)

All results of one run are written in ONE transaction: either everything is
there, or nothing (and the run is marked failed with the error message).

When does it actually run
-------------------------
  python src/score_job.py            only if a grade was entered since the
                                     last successful run, otherwise it stops
                                     after one query ("nothing changed")
  python src/score_job.py --force    always (the nightly run: also picks up
                                     attendance and edited marks, which the
                                     quick check cannot see)
  python src/score_job.py --dry-run  computes and prints, writes nothing

Connection: EDUDEVICE_DB_URL (the same variable as the API), e.g.
  mysql+pymysql://jorik:PASSWORD@127.0.0.1:3306/edudevice_db

The absence rules, the year grade (per trimester) and the possible range are
not copied here: they are imported from the backend
(backend/app/services/attendance_stats.py and final_range.py), so the page
and the job can never disagree about a percentage, an average or "secured".
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text

import backend_rules
import model_store
import notenstatistiken as ns
import prognosis_school
import scoring

DSP_DIR = Path(__file__).resolve().parent.parent
URL_ENV_VAR = "EDUDEVICE_DB_URL"
INSIGHT_MODEL = "insights-v1"
RANGE_MODEL = "range-v3"           # v3: per trimester, coming trimesters open (final_range.py)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def school_year_id(con, label: str) -> int:
    row = con.execute(text("SELECT id FROM school_years WHERE label = :l"), {"l": label}).first()
    if row is None:
        raise SystemExit(f"school year '{label}' not found")
    return row[0]


def nothing_changed(con) -> bool:
    """True if no grade was entered since the last successful run."""
    last = con.execute(text("SELECT MAX(started_at) FROM pipeline_runs WHERE status = 'success'")).scalar()
    newest = con.execute(text("SELECT MAX(created_at) FROM grades")).scalar()
    return last is not None and (newest is None or newest <= last)


def load_last_days(con, year_id: int) -> dict[int, date]:
    """class_subject_id -> last lesson day. Same as the API (statistics._trimesters_per_subject):
    the class's last day (5th classes: 30 April), otherwise the school year's."""
    return {cs: last for cs, last in con.execute(text("""
            SELECT cs.id, COALESCE(c.last_lesson_day, y.last_lesson_day, y.end_date)
            FROM class_subjects cs
                JOIN classes c      ON c.id = cs.class_id
                JOIN school_years y ON y.id = c.school_year_id
            WHERE c.school_year_id = :y"""), {"y": year_id})}


def current_trimester(con, year_id: int, today: date) -> int | None:
    """id of the trimester today lies in - between two trimesters the one that ended last."""
    return con.execute(text("""
            SELECT id FROM trimesters WHERE school_year_id = :y AND start_date <= :d
            ORDER BY start_date DESC LIMIT 1"""), {"y": year_id, "d": today}).scalar()


def load_attendance(con, year_id: int, today: date, rules) -> tuple[dict, dict]:
    """Same rules as the API (statistics._attendance):
    {(student, cs): absence_summary} and {student: [(date, minutes_missed), ...]} for held lessons."""
    lessons = {}
    total, held, n_lessons = defaultdict(int), defaultdict(int), defaultdict(int)
    held_by_cs = defaultdict(list)
    for lid, day, cancelled, cs, minutes, last_day in con.execute(text("""
            SELECT l.id, l.date, l.cancelled, t.class_subject_id,
                   TIME_TO_SEC(TIMEDIFF(t.end_time, t.start_time)) DIV 60,
                   COALESCE(c.last_lesson_day, y.last_lesson_day)
            FROM lessons l
                JOIN timetable t       ON t.id = l.timetable_id
                JOIN class_subjects cs ON cs.id = t.class_subject_id
                JOIN classes c         ON c.id = cs.class_id
                JOIN school_years y    ON y.id = c.school_year_id
            WHERE c.school_year_id = :y"""), {"y": year_id}):
        if last_day is not None and day > last_day:
            continue
        minutes = int(minutes)
        lessons[lid] = (cs, minutes, day, bool(cancelled))
        total[cs] += minutes
        n_lessons[cs] += 1
        if day <= today:
            held[cs] += minutes
            if not cancelled:
                held_by_cs[cs].append((lid, day))

    missed, unknown = defaultdict(int), defaultdict(int)
    missed_in = {}                                     # (student, lesson) -> minutes
    for sid, lid, status, minutes in con.execute(text("""
            SELECT a.student_id, a.lesson_id, a.status, a.minutes_missed
            FROM attendance a
                JOIN lessons l         ON l.id = a.lesson_id
                JOIN timetable t       ON t.id = l.timetable_id
                JOIN class_subjects cs ON cs.id = t.class_subject_id
                JOIN classes c         ON c.id = cs.class_id
            WHERE c.school_year_id = :y AND a.status <> 'anwesend'"""), {"y": year_id}):
        if lid not in lessons:
            continue
        cs, lesson_minutes, _, cancelled = lessons[lid]
        if cancelled:
            continue
        if minutes is None:
            if status == "abwesend":
                missed[(sid, cs)] += lesson_minutes
                missed_in[(sid, lid)] = lesson_minutes
            else:
                unknown[(sid, cs)] += 1
            continue
        missed[(sid, cs)] += int(minutes)
        missed_in[(sid, lid)] = int(minutes)

    enrolled = defaultdict(set)
    for cs, sid in con.execute(text("SELECT class_subject_id, student_id FROM class_subject_students")):
        enrolled[cs].add(sid)

    summaries, held_per_student = {}, defaultdict(list)
    for cs, students in enrolled.items():
        if cs not in total:
            continue
        for sid in students:
            summaries[(sid, cs)] = rules.absence_summary(total[cs], held[cs], missed[(sid, cs)],
                                                         unknown[(sid, cs)], n_lessons[cs])
            held_per_student[sid] += [(day, missed_in.get((sid, lid), 0)) for lid, day in held_by_cs[cs]]
    return summaries, held_per_student


# ---------------------------------------------------------------------------
# Computing
# ---------------------------------------------------------------------------

def load_model(root: Path, name: str, without: str):
    """(model, card) from the model store, or (None, None) with a warning."""
    try:
        model, card, _ = model_store.load(name, "latest", root)
        return model, card
    except FileNotFoundError as e:
        print(f"WARNING: {e}\n         {without}", file=sys.stderr)
        return None, None


def compute(data: dict, absences: dict, held_per_student: dict, bundle, card, today: date,
            last_days: dict, ranges) -> dict:
    """bundle, card: the prognosis model (both None without one).
    last_days: {cs: last lesson day}; ranges: backend final_range.py."""
    windows = data["trimesters"]
    base = [(t["start_date"], t["end_date"]) for t in sorted(windows, key=lambda t: t["number"])]
    tris = defaultdict(lambda: base)            # per class_subject, cut at the class's last day
    tris.update({cs: ranges.clip_to(base, last) for cs, last in last_days.items()})

    def trimester_of(day):
        for t in windows:
            if t["start_date"] <= day <= t["end_date"]:
                return t["number"]
        return None

    # The chance to fail comes from the prognosis model too (prognosis_school.fail_probability),
    # so the teacher's number and the likely band cannot contradict each other.
    model_note = (f"model {card.name} v{card.version}"
                  + (", trained on simulated data" if card.synthetic_training_data else "")
                  if card else "")
    version = (f"{card.name}-v{card.version}+{RANGE_MODEL}" if card else RANGE_MODEL)[:50]

    by_pair = defaultdict(list)
    for r in data["grades"]:
        by_pair[(r.student_id, r.class_subject_id)].append(
            scoring.DatedMark(r.category, r.value, r.weight, r.on))
    likely = prognosis_school.predict_current(bundle, by_pair, tris, today) if bundle else {}

    assessments, alerts, forecasts, candidates = [], [], [], defaultdict(list)
    for (sid, cs), marks in by_pair.items():
        raw = scoring.subject_raw(marks, tris[cs])
        if raw is None:
            continue
        # still possible: coming trimesters, the rest of the current one, missing parts
        r = ranges.final_range([(m.component, m.value, m.weight, m.date) for m in marks], tris[cs], today)
        env = scoring.Envelope(raw, r.low, r.high, r.status, r.required)
        absence = absences.get((sid, cs))
        forecast = likely.get((sid, cs))
        p = forecast["fail_probability"] if forecast and env.status == "undecided" else None
        # (decided by the rules: no model needed)
        point = min(max(raw, env.low), env.high)
        assessments.append({
            "student_id": sid, "class_subject_id": cs, "model_version": version,
            "status": env.status, "fail_probability": p,
            "predicted_final": round(point, 2), "predicted_low": round(env.low, 2),
            "predicted_high": round(env.high, 2),
            # shortly before the end very little is open, so the needed average can be
            # far outside 4-10; the column holds -99.99 to 99.99, and the sign is what matters
            "required_remaining_avg": None if env.required is None
                                      else round(min(max(env.required, Decimal(-99)), Decimal(99)), 2),
            "absence_rate": absence["rate"] if absence else 0,
        })
        if forecast:
            # the likely range never claims what the rules exclude: clip it into the possible range
            lo, hi = float(env.low), float(env.high)
            f_low, f_point, f_high = (round(min(max(forecast[k], lo), hi), 2) for k in ("low", "point", "high"))
            forecasts.append({"student_id": sid, "class_subject_id": cs, "predicted_grade": f_point,
                              "predicted_low": f_low, "predicted_high": f_high, "model_version": version})
        for a in scoring.alerts_for(env, p, absence, marks, today, model_note):
            alerts.append({"student_id": sid, "class_subject_id": cs, "type": a.type,
                           "severity": a.severity, "message": a.message})
        candidates[sid] += scoring.subject_insights(cs, marks, raw, absence, today, trimester_of, tris[cs])

    for sid, held in held_per_student.items():
        clean = scoring.attendance_streak(held, today)
        if clean:
            candidates[sid].append(clean)

    insights = []
    for sid, cands in candidates.items():
        for i in scoring.pick(cands):
            insights.append({"student_id": sid, "class_subject_id": i.class_subject_id, "kind": i.kind,
                             "tone": i.tone, "score": round(i.score, 3), "message": i.message})
    return {"assessments": assessments, "alerts": alerts, "forecasts": forecasts,
            "insights": insights, "version": version}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write(con, run_id: int, result: dict, year_start: date, today: date,
          trimester_id: int | None) -> int:
    if result["assessments"]:
        con.execute(text("""
            INSERT INTO risk_assessments (student_id, class_subject_id, model_version, status,
                fail_probability, predicted_final, predicted_low, predicted_high,
                required_remaining_avg, absence_rate)
            VALUES (:student_id, :class_subject_id, :model_version, :status, :fail_probability,
                :predicted_final, :predicted_low, :predicted_high, :required_remaining_avg,
                :absence_rate)"""), result["assessments"])

    # Alerts only once: attendance limits once per school year, the others while
    # an earlier one of the same kind is still open / recent.
    new_alerts = []
    for a in result["alerts"]:
        if a["type"] in ("attendance_20", "attendance_30"):
            since, open_only = year_start, False
        elif a["type"] == "deterioration":
            since, open_only = date.fromordinal(today.toordinal() - scoring.RECENT_DAYS), False
        else:
            since, open_only = year_start, True
        exists = con.execute(text(f"""
            SELECT 1 FROM alerts WHERE student_id = :s AND class_subject_id = :c AND type = :t
              AND created_at >= :since {"AND acknowledged_at IS NULL" if open_only else ""} LIMIT 1"""),
            {"s": a["student_id"], "c": a["class_subject_id"], "t": a["type"], "since": since}).first()
        if not exists:
            new_alerts.append(a)
    if new_alerts:
        con.execute(text("""
            INSERT INTO alerts (student_id, class_subject_id, type, severity, message)
            VALUES (:student_id, :class_subject_id, :type, :severity, :message)"""), new_alerts)

    if result["forecasts"] and trimester_id is not None:
        con.execute(text("""
            INSERT INTO grade_forecasts (run_id, student_id, class_subject_id, trimester_id,
                predicted_grade, predicted_low, predicted_high, model_version)
            VALUES (:run_id, :student_id, :class_subject_id, :trimester_id, :predicted_grade,
                :predicted_low, :predicted_high, :model_version)"""),
            [dict(f, run_id=run_id, trimester_id=trimester_id) for f in result["forecasts"]])

    if result["insights"]:
        week = scoring.week_start(today)
        con.execute(text("""
            INSERT INTO student_insights (run_id, student_id, class_subject_id, week_start, kind, tone,
                score, message, model_version)
            VALUES (:run_id, :student_id, :class_subject_id, :week, :kind, :tone, :score, :message,
                :model_version)"""),
            [dict(i, run_id=run_id, week=week, model_version=INSIGHT_MODEL) for i in result["insights"]])
    result["new_alerts"] = len(new_alerts)
    return len(result["assessments"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=None, help=f"default: ${URL_ENV_VAR}")
    ap.add_argument("--year", default="2026/27", help="school year label")
    ap.add_argument("--force", action="store_true", help="run even if no new grade came in")
    ap.add_argument("--dry-run", action="store_true", help="compute and print, write nothing")
    ap.add_argument("--today", type=date.fromisoformat, default=None, help="for testing only")
    ap.add_argument("--models", default=str(DSP_DIR / "models"), help="model store folder")
    args = ap.parse_args()

    url = args.url or os.environ.get(URL_ENV_VAR)
    if not url:
        raise SystemExit(f"set {URL_ENV_VAR} (or pass --url)")
    engine = create_engine(url, pool_pre_ping=True)
    today = args.today or date.today()
    rules = backend_rules.load("attendance_stats")
    ranges = backend_rules.load("final_range")

    with engine.connect() as con:
        if not args.force and not args.dry_run and nothing_changed(con):
            print(f"{datetime.now():%Y-%m-%d %H:%M} nothing changed since the last run")
            return
        year_id = school_year_id(con, args.year)
        year_start = con.execute(text("SELECT start_date FROM school_years WHERE id = :y"),
                                 {"y": year_id}).scalar()
        absences, held = load_attendance(con, year_id, today, rules)
        last_days = load_last_days(con, year_id)
        trimester_id = current_trimester(con, year_id, today)

    data = ns.load(engine, year_id)
    bundle, card = load_model(Path(args.models), prognosis_school.MODEL_NAME,
                              "no likely range and no chance to fail until the prognosis model is trained.")
    result = compute(data, absences, held, bundle, card, today, last_days, ranges)

    if args.dry_run:
        print(f"dry run: {len(result['assessments'])} assessments, {len(result['forecasts'])} forecasts, "
              f"{len(result['alerts'])} alert candidates, {len(result['insights'])} observations "
              f"({result['version']})")
        for i in result["insights"][:12]:
            print(f"  student {i['student_id']:>3}  {i['tone']:<9} {i['kind']:<16} {i['message']}")
        return

    # The run row is committed on its own, so a failed run stays visible.
    with engine.begin() as con:
        run_id = con.execute(text("INSERT INTO pipeline_runs (model_version, status) VALUES (:v, 'running')"),
                             {"v": result["version"]}).lastrowid
    try:
        with engine.begin() as con:                     # everything or nothing
            n = write(con, run_id, result, year_start, today, trimester_id)
        with engine.begin() as con:
            con.execute(text("""UPDATE pipeline_runs SET status = 'success', finished_at = NOW(),
                                rows_processed = :n WHERE run_id = :r"""), {"n": n, "r": run_id})
    except Exception as e:
        with engine.begin() as con:
            con.execute(text("""UPDATE pipeline_runs SET status = 'failed', finished_at = NOW(),
                                error_message = :e WHERE run_id = :r"""),
                        {"e": f"{e}\n{traceback.format_exc()}"[:60000], "r": run_id})
        raise
    print(f"{datetime.now():%Y-%m-%d %H:%M} run {run_id}: {n} assessments, "
          f"{len(result['forecasts'])} forecasts, {result['new_alerts']} new alerts, "
          f"{len(result['insights'])} observations ({result['version']})")


if __name__ == "__main__":
    main()
