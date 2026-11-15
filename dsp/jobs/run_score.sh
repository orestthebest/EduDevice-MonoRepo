#!/usr/bin/env bash
# run_score.sh - what cron calls to run the scoring job (score_job.py).
#
# cron starts programs with an almost empty environment: no EDUDEVICE_DB_URL,
# no virtual environment, a different working directory. This script sets all
# of that up, makes sure two runs never overlap, and writes everything to a
# monthly log file in dsp/logs/.
#
#   bash run_score.sh            quick check: only runs if a grade came in
#   bash run_score.sh --force    full run (the nightly one)
#
# The DB password lives in ~/.edudevice_job.env (chmod 600, never in git):
#   EDUDEVICE_DB_URL='mysql+pymysql://jorik:PASSWORD@127.0.0.1:3306/edudevice_db'

set -euo pipefail

DSP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${EDUDEVICE_JOB_ENV:-$HOME/.edudevice_job.env}"
PYTHON="$DSP_DIR/.venv/bin/python"
LOCK="/tmp/edudevice_score_job.lock"
LOG_DIR="$DSP_DIR/logs"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/score_$(date +%Y-%m).log"

{
    echo "----- $(date '+%Y-%m-%d %H:%M:%S') start ${*:-(quick check)}"
    if [ ! -r "$ENV_FILE" ]; then
        echo "FAILED: settings file $ENV_FILE not found"
        exit 2
    fi
    set -a; . "$ENV_FILE"; set +a          # load EDUDEVICE_DB_URL into the environment
    cd "$DSP_DIR"

    # -n: if the previous run is still busy, skip this one instead of queueing up
    set +e
    flock -n -E 75 "$LOCK" "$PYTHON" src/score_job.py "$@"
    rc=$?
    set -e
    case $rc in
        0)  echo "ok" ;;
        75) echo "skipped: the previous run is still busy" ;;
        *)  echo "FAILED (exit $rc) - see the error above" ;;
    esac
    exit $rc
} >> "$LOG" 2>&1