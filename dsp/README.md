# EduDevice — Data Science component

Jorik Kuci · HTL Shkodër · Diplomarbeit 2026/27
Team: Gridi Bushati (server/API), Orest Bashi (UI/media)

This folder is the data-science half of EduDevice: it reads the school database,
computes the grade statistics the device displays, trains the risk model, and
hands both out as one JSON payload.

---

## 1. Setup, once

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then set the database URL. Never put the password in a file that goes in Git:

```bash
export EDUDEVICE_DB_URL="mysql+pymysql://USER:PASSWORD@HOST:3306/edudevice_db"
```

Windows PowerShell:

```powershell
$env:EDUDEVICE_DB_URL = "mysql+pymysql://USER:PASSWORD@HOST:3306/edudevice_db"
```

Every script reads this variable, so you only set it once per terminal. If you
open a new terminal you have to set it again.

---

## 2. Run order

Nothing here creates folders by hand. `models/`, `data/processed/` and
`data/processed_school/` are made by the code the first time they are needed.

There are **two tracks**. Track A is the OULAD pipeline — it runs on real,
non-circular data and is what proves the method works. Track B is the school
pipeline — it runs on the generated data and is what the device will show.
They meet at the data contract, so the code after the adapters is the same.

### Step 0 — connection (only for anything that touches the school database)

The school database is reachable only through an SSH tunnel. DataGrip builds
that tunnel itself; **a Python script does not**. Open one in its own window
and leave it open:

```bash
ssh -L 3306:localhost:3306 <ssh-benutzer>@172.20.1.115
```

Then, in the window you run Python from:

```bash
export EDUDEVICE_DB_URL="mysql+pymysql://jorik:PASSWORT@localhost:3306/edudevice_db"
```

Windows PowerShell:

```powershell
$env:EDUDEVICE_DB_URL = "mysql+pymysql://jorik:PASSWORT@localhost:3306/edudevice_db"
```

The password never goes into a file. Every script reads this variable, so it is
set once per terminal; a new terminal needs it again.

---

### Track A — OULAD (the evidence)

```bash
# A1  OULAD CSVs -> contract tables          (needs data/raw, no database)
python src/oulad_adapter.py

# A2  snapshots + features                   -> data/processed/features_v1.parquet
python src/snapshots.py

# A3  risk model on real data
python src/model_risk.py

# A4  optional: forecast with uncertainty band, drop detection
python src/model_prognosis.py
python src/anomaly.py
```

A1 must run before A2, and A2 before A3. These four need no database at all.

---

### Track B — school data (what the device shows)

**B0 — Gridi loads the two SQL files on the server**

```sql
SOURCE sim_trimesters.sql;
SOURCE sim_seed_edudevice.sql;
```

**The order of these two does not matter.** The seed file never touches the
`trimesters` table, and the trimesters file never touches `users` or `grades`,
so there is no foreign key between them. Both orders have been tested and give
the identical result: 3 trimesters, 50 students, 125 enrolments, 2297 grades.

What *does* matter is that **both are loaded before B2**. The statistics work
out which trimester a mark belongs to by checking its `date` against the
trimester windows. With `trimesters` empty, every mark falls outside all three
windows, and the per-trimester figures and the trend come back empty.

**B1 — regenerate the seed** (only if you change the generator)

```bash
python src/seed_edudevice_real.py --per-class 25 --seed 20261025 --out .
```

| file | goes to | what it is |
|---|---|---|
| `sim_seed_edudevice.sql` | Gridi | students, enrolments, grades |
| `sim_trimesters.sql` | Gridi | the three trimester date windows |
| `sim_ground_truth.json` | keep | which archetype each student was built from — the answer key |
| `sim_preview.csv` | keep | every generated mark, for eyeballing in Excel |

The seed is deterministic: same `--seed`, same output, byte for byte. Keep
`20261025` so the numbers in the Diplomarbeit stay reproducible.

**B2 — compute, train, display**

```bash
# a) the statistics on their own (no model needed)
python src/notenstatistiken.py --role admin --user-id 1 --school-year 1

# b) train the risk model and save it             -> models/risk_school/v1/
python src/risk_school.py --school-year 1 --source school_sim

# c) the statistics WITH the model predictions merged in
python src/notenstatistiken.py --role schueler --user-id 11 --school-year 1 \
    --with-predictions --out payload.json
```

Use `--out` rather than `>`. In Windows PowerShell the `>` operator writes
UTF-16 with a byte-order mark, which `json.load` cannot read; `--out` always
writes UTF-8.

`(b)` must run before `(c)`. `(c)` loads the saved model from `models/`, and
with nothing saved it stops with
`no saved model 'risk_school' under models/ - train one first`.

`--user-id` is the student's `users.id`, not a row number. Look one up with:

```sql
SELECT id, username, first_name, last_name FROM users WHERE username LIKE 'sim\_%' LIMIT 5;
```

**B3 — optional: the school data through the contract**

```bash
python src/school_adapter.py          # -> data/processed_school/
```

Only needed to run the OULAD-side models on school data. The statistics in B2
do not use it.

---

### Step 4 — inspect what you trained

```bash
python src/model_store.py              # list every saved model
python src/model_store.py risk_school  # the full card for the newest version
```

### Tests, at any point

```bash
python -m pytest -q
```

78 pass. Seven contract tests skip unless `EDUDEVICE_DB_URL` points at a
database with the school tables — that is expected, not a failure.

---

## 3. `models/` — created by the code, never by hand

You do not make this folder. `risk_school.py` creates it on the first training
run, through `model_store.save()`:

```
models/
└── risk_school/
    └── v1/
        ├── model.joblib    the fitted scikit-learn pipeline
        ├── card.json       what it was trained on, which features, in which order
        └── metrics.json    how it scored on the held-out students
```

Each training run makes the **next** version — `v1`, then `v2`, `v3`. Nothing is
ever overwritten, so an old model stays loadable after a retrain and you can
show the progression in the Diplomarbeit. `model_store.load("risk_school")`
resolves to the highest version unless you ask for a specific one.

`models/` is in `.gitignore`: a `.joblib` is a binary blob, it is reproducible
from the seed, and committing a 50 kB binary on every retrain bloats the repo.
The `card.json` is the part worth quoting, and you quote it in the text.

---

## 4. What the two model files are for

They are not duplicates.

| file | trained on | features | use |
|---|---|---|---|
| `model_risk.py` | OULAD | clicks, submissions, VLE engagement | the method chapter — a real dataset, non-circular metrics |
| `risk_school.py` | the school DB | grades only | the device — the only features the school actually stores |

`model_risk.py` is what proves the approach works, because OULAD is real data.
`risk_school.py` is what runs on the Pi. Keep both and say exactly this in the
write-up: it is the honest version and it is also the stronger argument.

---

## 5. The one thing that must be said out loud

`risk_school` is currently trained on data that `seed_edudevice_real.py`
invented. The model has rediscovered the rules the generator used, so its
ROC-AUC of 0.97 is **circular**. It demonstrates that the pipeline runs
end to end. It is not evidence that the method works.

This is not a disclaimer to bury. `card.json` carries
`synthetic_training_data: true`, `model_store.describe()` prints a WARNING
block, and `notenstatistiken.py --with-predictions` writes a note to stderr on
every run. Say it plainly in the Diplomarbeit before anyone asks — the OULAD
model is where the real numbers come from.

---

## 6. Files

```
src/
  grade_stats.py            the grading arithmetic: category -> M1/M2/M3, 40/40/20, rounding
  notenstatistiken.py       Ziel M-3: statistics + predictions, role-gated, as JSON
  rules.py                  the original rule layer (pass/fail status, attendance, best/worst case)
  risk_school.py            risk model on school grades            -> models/risk_school/
  model_store.py            save / load / describe trained models
  model_risk.py             risk model on OULAD
  model_prognosis.py        grade forecast with uncertainty band (O-3, not yet persisted)
  anomaly.py                EWMA control chart for sudden drops
  contract.py               the shared table shapes both adapters must produce
  oulad_adapter.py          OULAD CSVs    -> the contract
  school_adapter.py         the school DB -> the contract
  snapshots.py              temporal cutoffs, so no model sees the future
  generate_school_data.py   the older standalone generator (pre-real-schema)
  seed_edudevice_real.py    the generator that writes SQL for the real schema

tests/
  test_grade_stats.py       the school's grading rules
  test_rules.py             the rule layer
  test_contract.py          both adapters produce the same shape

data/
  raw/                      OULAD CSVs from Kaggle (443 MB, not in Git)
  processed/                parquet output, written by the code
```

### Tests

```bash
python -m pytest -q
```

74 pass. The contract tests skip unless `data/raw` has the OULAD CSVs and
`EDUDEVICE_DB_URL` is set — that is expected, not a failure.

---

## 7. Open questions, not yet decided

- **Trimester dates** in `seed_edudevice_real.py` are a guess
  (7 Sep–4 Dec, 7 Dec–19 Mar, 22 Mar–2 Jul). Confirm the real ones with the
  Sekretariat and regenerate.
- **`FRAGILE_BELOW = 5.5`** in `notenstatistiken.py` is a choice, not a school
  rule. `FAIL_BELOW = 4.6` *is* the rule. Confirm the warning band with
  Prof. Opitz.
- **`risk_assessments`** needs `absence_rate`, `predicted_final`,
  `predicted_low` and `predicted_high` as `NOT NULL`. There is no attendance
  data in the school database and no forecast for school data yet, so these
  cannot be filled honestly. See `decisions.md`.
- **Teacher view on the device** currently gives aggregates plus a named
  at-risk list, not the full class roster. Confirm that is what a teacher
  should see on a shared screen.