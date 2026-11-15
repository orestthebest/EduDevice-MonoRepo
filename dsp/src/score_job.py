"""
score_job.py — the nightly scoring job (runs from cron, or by hand).

What one run does
-----------------
For every student in every subject of the school year:

  risk_assessments   status (secured / undecided / cannot pass), the possible
                     range of the final grade, the needed average, the absence
                     rate, and the fail probability of the risk model
                     (NULL when the rules already decide the outcome)
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

The absence rules are not copied here: they are imported from the backend
(backend/app/services/attendance_stats.py), so the page and the job can never
disagree about a percentage.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import traceback
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, text

import model_store
import notenstatistiken as ns
import risk_school
import scoring
from grade_stats import Mark, component_grade

DSP_DIR = Path(__file__).resolve().parent.parent
BACKEND_RULES = DSP_DIR.parent / "backend" / "app" / "services" / "attendance_stats.py"
URL_ENV_VAR = "EDUDEVICE_DB_URL"
INSIGHT_MODEL = "insights-v1"
RANGE_MODEL = "envelope-v1"


def load_attendance_rules():
    """The backend's attendance_stats.py, loaded by path (it has no dependencies)."""
    if not BACKEND_RULES.exists():
        raise FileNotFoundError(f"{BACKEND_RULES} not found - score_job.py must run inside the "
                                "monorepo (dsp/ next to backend/)")
    spec = importlib.util.spec_from_file_location("attendance_stats", BACKEND_RULES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

def load_model(root: Path):
    try:
        model, card, _ = model_store.load(risk_school.MODEL_NAME, "latest", root)
        return model, card
    except FileNotFoundError as e:
        print(f"WARNING: {e}\n         fail probabilities stay empty until a model is trained.",
              file=sys.stderr)
        return None, None


def compute(data: dict, absences: dict, held_per_student: dict, model, card, today: date) -> dict:
    windows = data["trimesters"]

    def trimester_of(day):
        for t in windows:
            if t["start_date"] <= day <= t["end_date"]:
                return t["number"]
        return None

    # The risk model is trained on snapshots "after trimester k" - give it the
    # trimesters that have started, not all three of the year.
    probabilities = {}
    if model is not None:
        started = dict(data, trimesters=[t for t in windows if t["start_date"] <= today])
        probabilities = risk_school.predict_current(started, model, card)
    model_note = (f"model {card.name} v{card.version}"
                  + (", trained on simulated data" if card.synthetic_training_data else "")
                  if card else "")
    version = (f"{card.name}-v{card.version}+{RANGE_MODEL}" if card else RANGE_MODEL)[:50]

    by_pair = defaultdict(list)
    for r in data["grades"]:
        by_pair[(r.student_id, r.class_subject_id)].append(
            scoring.DatedMark(r.category, r.value, r.weight, r.on))

    assessments, alerts, candidates = [], [], defaultdict(list)
    for (sid, cs), marks in by_pair.items():
        plain = [Mark(m.category, m.value, m.weight) for m in marks]
        comps = {k: component_grade(plain, k).raw for k in ("M1", "M2", "M3")}
        raw = scoring.subject_raw(marks)
        if raw is None:
            continue
        env = scoring.envelope(comps, raw)
        absence = absences.get((sid, cs))
        p = probabilities.get((sid, cs), {}).get("fail_probability")
        p = p if env.status == "undecided" else None          # decided by the rules: no model needed
        point = min(max(raw, env.low), env.high)
        assessments.append({
            "student_id": sid, "class_subject_id": cs, "model_version": version,
            "status": env.status, "fail_probability": p,
            "predicted_final": round(point, 2), "predicted_low": round(env.low, 2),
            "predicted_high": round(env.high, 2),
            "required_remaining_avg": None if env.required is None else round(env.required, 2),
            "absence_rate": absence["rate"] if absence else 0,
        })
        for a in scoring.alerts_for(env, p, absence, marks, today, model_note):
            alerts.append({"student_id": sid, "class_subject_id": cs, "type": a.type,
                           "severity": a.severity, "message": a.message})
        candidates[sid] += scoring.subject_insights(cs, marks, raw, absence, today, trimester_of)

    for sid, held in held_per_student.items():
        clean = scoring.attendance_streak(held, today)
        if clean:
            candidates[sid].append(clean)

    insights = []
    for sid, cands in candidates.items():
        for i in scoring.pick(cands):
            insights.append({"student_id": sid, "class_subject_id": i.class_subject_id, "kind": i.kind,
                             "tone": i.tone, "score": round(i.score, 3), "message": i.message})
    return {"assessments": assessments, "alerts": alerts, "insights": insights, "version": version}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def write(con, run_id: int, result: dict, year_start: date, today: date) -> int:
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
    rules = load_attendance_rules()

    with engine.connect() as con:
        if not args.force and not args.dry_run and nothing_changed(con):
            print(f"{datetime.now():%Y-%m-%d %H:%M} nothing changed since the last run")
            return
        year_id = school_year_id(con, args.year)
        year_start = con.execute(text("SELECT start_date FROM school_years WHERE id = :y"),
                                 {"y": year_id}).scalar()
        absences, held = load_attendance(con, year_id, today, rules)

    data = ns.load(engine, year_id)
    model, card = load_model(Path(args.models))
    result = compute(data, absences, held, model, card, today)

    if args.dry_run:
        print(f"dry run: {len(result['assessments'])} assessments, {len(result['alerts'])} alert "
              f"candidates, {len(result['insights'])} observations ({result['version']})")
        for i in result["insights"][:12]:
            print(f"  student {i['student_id']:>3}  {i['tone']:<9} {i['kind']:<16} {i['message']}")
        return

    # The run row is committed on its own, so a failed run stays visible.
    with engine.begin() as con:
        run_id = con.execute(text("INSERT INTO pipeline_runs (model_version, status) VALUES (:v, 'running')"),
                             {"v": result["version"]}).lastrowid
    try:
        with engine.begin() as con:                     # everything or nothing
            n = write(con, run_id, result, year_start, today)
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
          f"{result['new_alerts']} new alerts, {len(result['insights'])} observations "
          f"({result['version']})")


if __name__ == "__main__":
    main()
