# Decisions log

Every choice in this project that could have gone another way, why it went the
way it did, and which ones are still open. This is the file to read from when
writing the Diplomarbeit and the file to defend from at the Präsentation.

---

## Grading rules — facts, not choices

These come from the school. They are not design decisions and must not be
"improved".

**Grades run 4 to 10, where 10 is best and 4 is a fail.**

**Rounding is at .6, not at .5.** A computed average of 4.6 becomes a 5 and
passes; 4.5 stays a 4 and fails. Standard half-up rounding would promote every
student between 4.50 and 4.59 to a pass — exactly the students sitting closest
to the line. Implemented in `rules.round_final` (float, with an epsilon) and
`grade_stats.round_grade` (Decimal, exact). `test_grade_stats.py` compares the
two across the whole scale in 0.01 steps so they can never drift apart.

A consequence worth knowing: because the rule is .6, "raw average ≥ 4.6" and
"rounded grade ≥ 5" are exactly equivalent. The model's label and the display's
pass/fail test therefore agree by construction. Under half-up rounding they
would not have, and the model would have been predicting a different question
from the one the screen answers.

**Weighting is M1 40%, M2 40%, M3 20%.** M1 Mitarbeit, M2 Schularbeit,
M3 Projekt. The Projekt happens once per year, not once per trimester.

**A missing component is missing, never zero.** With only Mitarbeit graded, the
subject grade is the Mitarbeit figure, not a number dragged toward an invented
zero. The remaining weights are renormalised and the result is flagged
`provisional`. Treating an ungraded Schularbeit as a 0 would fail half the
school in October; this is the single most dangerous bug the project could
have, so it has its own test.

**Where the period lives is the database's decision, not ours.**
`period_grades` carries a CHECK:

```
(kind IN ('M1','M2') AND trimester_id IS NOT NULL)
OR (kind IN ('M3','FINAL') AND trimester_id IS NULL)
```

So M1 and M2 are per trimester, M3 and FINAL are per year. A Projekt graded in
October still counts for the year, not for trimester 1 — only the grade's
`date` moves, never the period it counts in. This settles the "which trimester
does the Projekt belong to" question without us having to pick. Verified
against the live schema: inserting an M3 with a `trimester_id` is rejected with
`ERROR 3819`.

---

## Choices we made

**Two risk models, kept separate.** `model_risk.py` (OULAD: clicks,
submissions, engagement) and `risk_school.py` (school: grades only). The school
database stores none of OULAD's features, so one model cannot serve both. The
OULAD model is where non-circular metrics come from; the school model is what
runs on the device.

**Grades-only feature set for the school model.** The `attendance` and
`homework` tables exist but are empty, so including them would mean training on
empty columns. When they fill up, the feature list grows and the model is
retrained — that is a new version in the model store, not a rewrite.

**Models are versioned directories, never overwritten.**
`models/<name>/v<N>/` holding `model.joblib`, `card.json`, `metrics.json`. An
old model stays loadable after a retrain, so the progression can be shown.

**The model card travels with the model.** `synthetic_training_data` is a field
on the card, not a note in a README, so a model and the warning about it cannot
be separated later.

**The JSON payload goes to stdout, warnings to stderr.** So
`notenstatistiken.py ... > payload.json` produces a file the API can parse,
while a human at a terminal still sees the synthetic-data warning.

**Role gating lives in the computation layer, not only in the UI.**
`view_for()` enforces it: a Schüler gets their own data and class comparisons
as aggregates only — never named classmates; a Lehrkraft gets only their own
`class_subjects`; an Admin gets everything. An unknown role is refused. Putting
this only in Orest's UI would mean the API would still serve the data to anyone
who asked.

**Pass mark and warning band are two different numbers.**
`FAIL_BELOW = 4.6` is the school's rule. `FRAGILE_BELOW = 5.5` is our choice of
warning band — a student above the line but close to it. These were one constant
at first (`AT_RISK_AT_OR_BELOW = 5`), which conflated a fact with a judgement.
Splitting them means the fact cannot be changed by accident and the judgement
is visible as a judgement.

**The seed is deterministic and has a ground-truth manifest.** Same `--seed`,
same bytes. `sim_ground_truth.json` records which archetype each student was
built from, so the pipeline can be checked against an answer key: all 8
student-subjects genuinely below the pass mark are flagged, and the 12 flagged
at ≥0.50 are exclusively the `failing` and `sudden_drop` archetypes.

**Archetypes are allocated by largest remainder, not by independent draws.**
Independent random draws gave 18 improving and 5 declining on one unlucky seed,
which is not a plausible class. Proportional allocation keeps the mix stable
across seeds.

**A `failing` archetype was added deliberately.** The first generator produced
only 6 failing rows in 250 — too few to train on, because it had no genuinely
weak students, only average ones having a bad trimester. The `failing`
archetype (ability 4.1–5.1) brings it to 16 of 250, which is 6.4% and close to
a real failure rate.

**Sim accounts get bcrypt hashes of discarded random passwords.** Not a shared
password, not a blank: nobody can log in as a sim student, including us.

**Sim data goes into the real database with a `sim_` marker.** Every student-
touching foreign key is `ON DELETE CASCADE` — verified on a throwaway MySQL
server, where deleting the sim users took grades from 907 to 2 and left zero
orphan rows. So `DELETE FROM users WHERE username LIKE 'sim\_%'` is a complete
cleanup, which is what makes it safe to put generated rows in the real schema
rather than maintaining a parallel one.

---

**Absence is counted in minutes against the whole year.** Five minutes late
are five minutes, not a lesson. The base is every lesson of the subject in the
year, up to the class's last teaching day (5th classes: 30 April). A cancelled
lesson still counts in that base - as if it had taken place - but nobody can be
absent in it. Excused or not does not matter for the limits (20 % exam, 30 %
not assessable). The projection "at your current pace" only appears once 15 %
of the year has passed; earlier, one missed lesson would project to 100 %.
The rules live once, in `backend/app/services/attendance_stats.py`; the
scoring job imports that file instead of copying it, and for all 125 sim
student-subjects the job and the API give identical numbers.

**The scoring job writes a range, not yet a forecast.** Until the prognosis
model exists, `predicted_low/high` in `risk_assessments` is the exact envelope
from the rules (missing parts all 4 / all 10) and `predicted_final` is today's
average. The page calls it "still possible", not "expected". The fail
probability is only computed where the rules leave the outcome open
(`undecided`) and is shown to teachers only - never to students.

**Observations need to beat the student's own noise.** A change is only
mentioned when it is large compared with that student's normal spread in the
subject (at least 1.5 grade points and 2 own standard deviations for a drop;
0.5 points and z >= 1.5 between trimesters). Three per week at most, at most
two warnings, at least one positive one when there is any. Messages describe
marks ("your marks are rising"), never the person, and never contain the
subject name - the page adds it.

**Trend labels are checked against the sim's known student types.** The
labels (rising / steady / falling / up and down / too early) come from a
Theil-Sen slope with a Kendall confidence interval, live in the API
(`backend/app/services/trend_stats.py`). Over the full simulated year:

| true type | rising | steady | falling | up and down | too early |
|---|---|---|---|---|---|
| improving | 22 | 3 | 0 | 0 | 0 |
| steady | 0 | 35 | 0 | 0 | 0 |
| declining | 0 | 3 | 13 | 0 | 0 |
| sudden_drop | 0 | 9 | 5 | 0 | 0 |
| volatile | 3 | 8 | 2 | 0 | 0 |
| failing | 0 | 13 | 0 | 0 | 0 |
| incomplete | 0 | 9 | 0 | 0 | 0 |

No subject ever gets the opposite direction. "Up and down" never fires: the
generator's volatile students swing between trimesters, but their single marks
scatter no more than a steady student's (robust spread median 0.78 vs 0.74), so
no threshold separates them without mislabelling improving or declining ones.
The threshold stays where it is; on real data it may fire, on the sim it
cannot be validated. Mid-year (13 November) almost everything is "steady" or
"too early" - after two months that is the honest answer. Same caveat as
everywhere: the sim was generated with these types, so this checks that the
method recovers a known pattern, not that it works on real students.

**Alerts fire once.** Attendance limits once per school year, fail risk while
an earlier one is unacknowledged, drops once per two weeks. A second run on
the same data adds no new alert.

## Mistakes worth remembering

**The 4.6 floating-point bug.** `round_final(4.6)` returned 4, because in
binary `4.6 - 4` is `0.5999999999999996`, which is not `>= 0.6`. Fixed with an
epsilon in `rules.py` and by working in `Decimal` in `grade_stats.py`. The
tempting fix — moving the threshold to 0.55 — would have silently changed a
school rule to paper over an error of 4×10⁻¹⁶.

**`grade_stats.round_grade` shipped using `ROUND_HALF_UP`.** The rewrite for
the real schema quietly replaced the .6 rule with standard rounding, which
turns 4.5 into a pass. Caught by writing the test *before* trusting the module.
`rules.py` had been right since September; the new module disagreed with it and
nothing noticed until the two were compared directly. Hence the cross-check
test.

**The collation landmine in the seed SQL.** The staging temporary table
declared `username VARCHAR(50)` with no `COLLATE`, so it inherited the database
default (`utf8mb4_0900_ai_ci` on MySQL 8) while the real `users.username` is
`utf8mb4_unicode_ci`. The join then died with
`ERROR 1267 Illegal mix of collations` — after the inserts, so it would have
looked like the file half-worked. Fixed by pinning the column and putting an
explicit `COLLATE` on the join, which takes precedence over both sides.

**Guessing the schema instead of asking for it.** The first seeder assumed a
`students` table, a `subject_id` column and M1/M2/M3 columns. None exist. The
rule now: ask for `SHOW CREATE TABLE` before writing SQL against a table.

**Doubting a correct claim about the schema.** The CASCADE behaviour was
asserted and doubted; the recon proved it right.

**Four source files were created but never written.** `grade_stats.py`,
`notenstatistiken.py`, `seed_edudevice_real.py` and `test_grade_stats.py` sat
at 0 bytes, so nothing new could run. Check `ls -l` after saving.

---

## Open — needs a decision from someone else

| question | who decides | why it matters |
|---|---|---|
| The real trimester start/end dates | Sekretariat | the windows in the generator are a guess; every per-trimester figure depends on them |
| `FRAGILE_BELOW = 5.5` | Prof. Opitz | it is our judgement, not a rule, and it decides who gets a warning |
| `risk_assessments.absence_rate NOT NULL` | Gridi | no attendance data exists; writing 0.0000 would claim perfect attendance for everyone. Either the column becomes nullable, or attendance gets generated too |
| `predicted_final` / `_low` / `_high` `NOT NULL` | us | `model_prognosis.py` forecasts with a conformal interval but runs on OULAD; it has no school-data version yet |
| Teacher view on a shared device | Prof. Opitz | currently aggregates plus a named at-risk list. Naming struggling students on a screen in a classroom is a real question |
| Does the device show a teacher view at all | Prof. Opitz | changes the whole interaction model, and Orest needs to know before designing |
