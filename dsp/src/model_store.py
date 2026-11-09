"""
model_store.py — saving, loading and describing trained models.

Until now every model was trained, printed to the terminal and thrown away. That
makes a model impossible to show, impossible to reproduce and impossible to put
behind an API. This module fixes that.

A saved model is a directory, not a single file:

    models/risk_school/v3/
        model.joblib      the fitted sklearn estimator
        card.json         everything needed to judge whether to trust it
        metrics.json      how it scored when it was trained

The card is the part that matters for the Diplomarbeit. It records what the
model was trained on, when, how many rows, which features in which order, and -
crucially - whether the training data was synthetic. A model trained on
generated data has learned the generator's rules, so its accuracy is circular
and must never be presented as evidence that the system works. The card carries
that warning with the model so the two cannot be separated later.

Versions are directories named v1, v2, ... and `latest` resolves to the highest.
Nothing is ever overwritten, so an old model stays loadable after a retrain.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import joblib

DEFAULT_ROOT = Path("models")


@dataclass
class ModelCard:
    """What a reader needs to decide whether this model's output means anything."""

    name: str
    task: str                       # "risk_classification" | "grade_forecast"
    version: int
    created_at: str
    data_source: str                # "oulad" | "school_sim" | "school_real"
    synthetic_training_data: bool
    n_training_rows: int
    n_positive: Optional[int] = None
    target: str = ""
    features: list[str] = field(default_factory=list)
    estimator: str = ""
    hyperparameters: dict = field(default_factory=dict)
    notes: str = ""
    sklearn_version: str = ""
    python_version: str = ""

    @property
    def trustworthy_for_evidence(self) -> bool:
        """False when the metrics are circular and may not be reported as results."""
        return not self.synthetic_training_data

    def warning(self) -> Optional[str]:
        if self.synthetic_training_data:
            return (
                "Trained on generated data. The model has rediscovered the rules the "
                "generator used, so its accuracy is circular. Use it to demonstrate "
                "the pipeline, never as evidence that the method works."
            )
        return None


def _version_dirs(root: Path, name: str) -> list[Path]:
    base = root / name
    if not base.exists():
        return []
    out = []
    for p in base.iterdir():
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit():
            out.append(p)
    return sorted(out, key=lambda p: int(p.name[1:]))


def next_version(root: Path | str, name: str) -> int:
    dirs = _version_dirs(Path(root), name)
    return (int(dirs[-1].name[1:]) + 1) if dirs else 1


def save(estimator: Any, card: ModelCard, metrics: dict,
         root: Path | str = DEFAULT_ROOT) -> Path:
    """Write the estimator, its card and its metrics as a new version directory."""
    import sklearn

    root = Path(root)
    card.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    card.estimator = type(estimator).__name__
    card.sklearn_version = sklearn.__version__
    card.python_version = platform.python_version()

    target = root / card.name / f"v{card.version}"
    target.mkdir(parents=True, exist_ok=False)

    joblib.dump(estimator, target / "model.joblib")
    (target / "card.json").write_text(
        json.dumps(asdict(card), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (target / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return target


def load(name: str, version: int | str = "latest",
         root: Path | str = DEFAULT_ROOT):
    """Return (estimator, card, metrics) for a saved model."""
    root = Path(root)
    if version == "latest":
        dirs = _version_dirs(root, name)
        if not dirs:
            raise FileNotFoundError(
                f"no saved model '{name}' under {root}/ - train one first"
            )
        target = dirs[-1]
    else:
        target = root / name / f"v{int(version)}"
        if not target.exists():
            raise FileNotFoundError(f"{target} does not exist")

    estimator = joblib.load(target / "model.joblib")
    card = ModelCard(**json.loads((target / "card.json").read_text(encoding="utf-8")))
    metrics = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
    return estimator, card, metrics


def list_models(root: Path | str = DEFAULT_ROOT) -> list[dict]:
    """Every saved model and version, newest version last."""
    root = Path(root)
    if not root.exists():
        return []
    out = []
    for base in sorted(p for p in root.iterdir() if p.is_dir()):
        for v in _version_dirs(root, base.name):
            card = json.loads((v / "card.json").read_text(encoding="utf-8"))
            metrics = json.loads((v / "metrics.json").read_text(encoding="utf-8"))
            out.append(
                {
                    "name": card["name"],
                    "version": card["version"],
                    "created_at": card["created_at"],
                    "data_source": card["data_source"],
                    "synthetic": card["synthetic_training_data"],
                    "n_rows": card["n_training_rows"],
                    "path": str(v),
                    "metrics": metrics,
                }
            )
    return out


def describe(name: str, version: int | str = "latest",
             root: Path | str = DEFAULT_ROOT) -> str:
    """A human-readable summary - what you show someone who asks about the model."""
    _, card, metrics = load(name, version, root)
    lines = [
        f"{card.name}  v{card.version}   ({card.task})",
        f"  trained      {card.created_at}",
        f"  source       {card.data_source}"
        + ("   [SYNTHETIC]" if card.synthetic_training_data else ""),
        f"  rows         {card.n_training_rows}"
        + (f"  ({card.n_positive} positive)" if card.n_positive is not None else ""),
        f"  estimator    {card.estimator}",
        f"  target       {card.target}",
        f"  features     {len(card.features)}: {', '.join(card.features)}",
        "  metrics",
    ]
    for k, v in metrics.items():
        lines.append(f"    {k:<24} {v}")
    if card.notes:
        lines.append(f"  notes        {card.notes}")
    w = card.warning()
    if w:
        lines += ["", "  WARNING", "    " + w]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Inspect saved models.")
    ap.add_argument("name", nargs="?", help="model name; omit to list everything")
    ap.add_argument("--version", default="latest")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    args = ap.parse_args()

    if args.name:
        print(describe(args.name, args.version, args.root))
    else:
        rows = list_models(args.root)
        if not rows:
            print(f"no saved models under {args.root}/")
        for r in rows:
            flag = "  [SYNTHETIC]" if r["synthetic"] else ""
            print(f"{r['name']:<20} v{r['version']:<3} {r['created_at']}  "
                  f"{r['data_source']:<12} {r['n_rows']:>6} rows{flag}")
