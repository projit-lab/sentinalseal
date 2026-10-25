"""
Measured accuracy, served to the Accuracy page.

Only results produced by real runs are shown. eval/evaluate.py writes
"provenance": "measured" at the top of results/metrics.json once every number
comes from running detector.analyze() on real files. Anything else is
reported as not measured, so the app can never display invented numbers.
"""

from __future__ import annotations

import json

from fastapi import APIRouter

from app.services.store import REPO_ROOT

router = APIRouter()

RESULTS_DIR = REPO_ROOT / "results"


def _load(name: str):
    path = RESULTS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@router.get("/metrics", summary="Measured test results (results/metrics.json)")
def metrics():
    data = _load("metrics.json")
    if data is None:
        return {"measured": False, "reason": "results/metrics.json not found. Run eval/evaluate.py."}
    if data.get("provenance") != "measured":
        return {"measured": False,
                "reason": "results/metrics.json is not marked as measured from real runs."}
    return {"measured": True, **data}


@router.get("/metrics/misses", summary="Failure cases from the last measured run")
def misses():
    data = _load("metrics.json")
    if not data or data.get("provenance") != "measured":
        return []
    items = _load("misses.json")
    return items if isinstance(items, list) else []
