"""
EduDevice - the data contract.

The single definition of what every adapter must return. OULAD and the school
database look nothing alike, but both are converted into these tables, which
is what lets the snapshot builder and the models run unchanged on either.

If a source cannot supply a table (OULAD has no real attendance, the school
has no click data), it is simply absent, and the snapshot builder picks
whichever is there. Columns inside a table, however, are not optional.
"""

from __future__ import annotations

import pandas as pd
from pandas.api import types as pdt

# table -> {column: kind}
# kinds: "int", "float", "date", "str", "id" (int or str), "any"
# course_id is an "id" because its form is up to the source: OULAD builds
# "AAA_2013J" from module and course run, the school uses the class_subject
# row id. Downstream code only ever groups and joins on it.
CONTRACT: dict[str, dict[str, str]] = {
    "enrollments": {
        "student_id": "int", "course_id": "id", "cohort_year": "int",
        "start_date": "date", "end_date": "date", "valid_until": "date",
        "failed": "float",          # float, because the running year is NaN
    },
    "grades": {
        "student_id": "int", "course_id": "id", "value": "float", "date": "date",
        "category": "str",
    },
    "assignments": {
        "course_id": "id", "assessment_id": "int", "due_date": "date",
    },
    "submissions": {
        "student_id": "int", "course_id": "id", "assessment_id": "int",
        "due_date": "date", "submitted_at": "date", "is_late": "int",
    },
    "final_grades": {
        "student_id": "int", "course_id": "id", "final_grade": "float",
    },
}

# At least one of these must be present: the attendance signal
ATTENDANCE_TABLES = {
    "attendance": {"student_id": "int", "course_id": "id", "date": "date",
                   "present": "int"},
    "engagement": {"student_id": "int", "course_id": "id", "date": "date",
                   "clicks": "int"},
}

REQUIRED_TABLES = set(CONTRACT)


def _kind_ok(series: pd.Series, kind: str) -> bool:
    if kind == "any":
        return True
    if kind == "date":
        return pdt.is_datetime64_any_dtype(series)
    if kind == "int":
        return pdt.is_integer_dtype(series) or pdt.is_bool_dtype(series)
    if kind == "float":
        return pdt.is_float_dtype(series) or pdt.is_integer_dtype(series)
    if kind == "str":
        # pandas 3 gives strings their own dtype; pandas 2 calls them objects
        return (pdt.is_string_dtype(series) or pdt.is_object_dtype(series)
                or isinstance(series.dtype, pd.CategoricalDtype))
    if kind == "id":
        return (pdt.is_integer_dtype(series) or pdt.is_string_dtype(series)
                or pdt.is_object_dtype(series))
    raise ValueError(f"unknown kind {kind}")


def validate(tables: dict[str, pd.DataFrame], source: str = "adapter") -> list[str]:
    """Return a list of contract violations; empty means the source is valid."""
    problems: list[str] = []

    for name in REQUIRED_TABLES:
        if name not in tables:
            problems.append(f"{source}: table '{name}' is missing")
            continue
        df = tables[name]
        for column, kind in CONTRACT[name].items():
            if column not in df.columns:
                problems.append(f"{source}.{name}: column '{column}' is missing")
            elif not _kind_ok(df[column], kind):
                problems.append(f"{source}.{name}.{column}: expected {kind}, "
                                f"got {df[column].dtype}")
        if df.empty:
            problems.append(f"{source}.{name}: table is empty")

    present = [n for n in ATTENDANCE_TABLES if n in tables]
    if not present:
        problems.append(f"{source}: needs an attendance signal "
                        f"('attendance' or 'engagement'), has neither")
    for name in present:
        for column, kind in ATTENDANCE_TABLES[name].items():
            if column not in tables[name].columns:
                problems.append(f"{source}.{name}: column '{column}' is missing")
            elif not _kind_ok(tables[name][column], kind):
                problems.append(f"{source}.{name}.{column}: expected {kind}, "
                                f"got {tables[name][column].dtype}")
    return problems


def assert_valid(tables: dict[str, pd.DataFrame], source: str = "adapter") -> None:
    problems = validate(tables, source)
    if problems:
        raise AssertionError("contract violations:\n  " + "\n  ".join(problems))
