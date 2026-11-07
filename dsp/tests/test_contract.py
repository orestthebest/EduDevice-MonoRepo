"""
Contract tests: both adapters must produce the same shape of data.

This is what keeps the two sources interchangeable. If someone later changes
a column in one adapter, these tests fail rather than the models silently
learning from something different.

Each source is skipped when it is not available, so the suite runs on a
laptop with only the OULAD CSVs, on the school server with only MySQL, or on
a machine with both.

Run:  pytest tests/test_contract.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from contract import CONTRACT, REQUIRED_TABLES, validate

OULAD_DIR = Path(os.environ.get("OULAD_DIR", "data/raw"))
# Same environment variable as the rest of the project. SCHOOL_DB_URL stays
# valid as the old name so nothing breaks.
SCHOOL_URL = os.environ.get("EDUDEVICE_DB_URL") or os.environ.get("SCHOOL_DB_URL", "")


# ---------------------------------------------------------------------
# Sources, loaded once
# ---------------------------------------------------------------------

@pytest.fixture(scope="session")
def oulad_tables():
    if not (OULAD_DIR / "studentInfo.csv").exists():
        pytest.skip(f"OULAD CSVs not found in {OULAD_DIR}")
    import oulad_adapter
    return oulad_adapter.build_all(OULAD_DIR, verbose=False)


@pytest.fixture(scope="session")
def school_tables():
    if not SCHOOL_URL:
        pytest.skip("EDUDEVICE_DB_URL not set")
    import school_adapter
    return school_adapter.build_all(SCHOOL_URL, verbose=False)


# ---------------------------------------------------------------------
# Each source on its own
# ---------------------------------------------------------------------

def test_oulad_satisfies_contract(oulad_tables):
    assert validate(oulad_tables, "oulad") == []


def test_school_satisfies_contract(school_tables):
    assert validate(school_tables, "school") == []


# ---------------------------------------------------------------------
# The two against each other
# ---------------------------------------------------------------------

def test_shared_columns_are_compatible(oulad_tables, school_tables):
    """A column both adapters produce must be usable the same way in both.

    Not byte-identical dtypes: int64 and float64 are both numbers and both
    work downstream. What must not happen is a date in one source and a
    string in the other.
    """
    families = {"i": "number", "u": "number", "f": "number", "b": "number",
                "M": "date", "m": "date", "O": "text", "U": "text", "T": "text"}
    mismatches = []
    for name in REQUIRED_TABLES:
        for column in CONTRACT[name]:
            left = oulad_tables[name][column].dtype.kind
            right = school_tables[name][column].dtype.kind
            if families.get(left, left) != families.get(right, right):
                if CONTRACT[name][column] == "id":
                    continue          # an id may be a number here and text there
                mismatches.append(f"{name}.{column}: oulad {left} vs school {right}")
    assert not mismatches, "incompatible columns:\n  " + "\n  ".join(mismatches)


def test_both_sources_build_the_same_features(oulad_tables, school_tables):
    """The feature builder must accept either source and return one schema."""
    from snapshots import FEATURES, build_features

    oulad_features = build_features(oulad_tables)
    school_features = build_features(school_tables)

    for name, features in (("oulad", oulad_features), ("school", school_features)):
        missing = set(FEATURES) - set(features.columns)
        assert not missing, f"{name} features missing {missing}"
        assert len(features) > 0, f"{name} produced no snapshots"


# ---------------------------------------------------------------------
# Invariants that matter more than types
# ---------------------------------------------------------------------

@pytest.mark.parametrize("source", ["oulad", "school"])
def test_grades_are_on_the_school_scale(source, request):
    tables = request.getfixturevalue(f"{source}_tables")
    values = tables["grades"]["value"]
    assert values.between(4, 10).all(), f"{source}: grades outside the 4-10 scale"


@pytest.mark.parametrize("source", ["oulad", "school"])
def test_no_duplicate_enrollments(source, request):
    tables = request.getfixturevalue(f"{source}_tables")
    duplicated = tables["enrollments"].duplicated(["student_id", "course_id"])
    assert not duplicated.any(), f"{source}: {duplicated.sum()} duplicate enrollments"


@pytest.mark.parametrize("source", ["oulad", "school"])
def test_grades_lie_inside_their_course(source, request):
    """A grade dated outside the course would corrupt every cutoff."""
    tables = request.getfixturevalue(f"{source}_tables")
    merged = tables["grades"].merge(
        tables["enrollments"][["student_id", "course_id", "start_date", "end_date"]],
        on=["student_id", "course_id"], how="inner")
    outside = (merged["date"] < merged["start_date"]) | (merged["date"] > merged["end_date"])
    assert outside.mean() < 0.01, (
        f"{source}: {outside.mean():.1%} of grades fall outside their course dates")


def test_school_running_year_has_no_label(school_tables):
    """The current year is what we predict; it must carry no outcome."""
    enrollments = school_tables["enrollments"]
    running = enrollments[enrollments["final_result"] == "Running"]
    assert len(running) > 0, "no running school year found"
    assert running["failed"].isna().all(), "running year must not carry a label"