"""
backend_rules.py — load a rules file from backend/app/services by its path.

Some rules must be identical on the page and in the nightly job (the absence
limits, what counts as "secured"). They live once, in the backend, as plain
Python files without dependencies. The DSP code loads them from there instead
of keeping a copy that could drift apart.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

BACKEND_SERVICES = Path(__file__).resolve().parents[2] / "backend" / "app" / "services"


def load(name: str):
    """backend/app/services/<name>.py as a module, e.g. load("final_range")."""
    path = BACKEND_SERVICES / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - the DSP code must run inside the "
                                "monorepo (dsp/ next to backend/)")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module