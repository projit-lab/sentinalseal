"""
SentinelSeal Detector — analyze(path) → verdict dict.

This is the single entry-point that Part B (backend) calls.
It **never raises**: any failure returns NEEDS_CALLBACK with a reason.
"""

from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path
from typing import Dict

from detector.contract import (
    NEEDS_CALLBACK,
    SUSPICIOUS,
    HIGH_THRESHOLD,
    make_verdict,
)

logger = logging.getLogger(__name__)


def analyze(path: str) -> Dict:
    """
    Analyse a video file for deepfake indicators.

    Parameters
    ----------
    path : str
        Absolute or relative path to a video file that OpenCV can read.

    Returns
    -------
    dict
        A verdict dict conforming to CONTRACT.md.
        Never raises — all failures become NEEDS_CALLBACK.
    """
    t0 = time.monotonic()

    try:
        p = Path(path)
        if not p.exists():
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[f"File not found: {p.name}"],
                processing_seconds=time.monotonic() - t0,
            )

        if not p.is_file():
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[f"Path is not a file: {p.name}"],
                processing_seconds=time.monotonic() - t0,
            )

        # ── Stub: return NEEDS_CALLBACK until the real pipeline is wired ──
        return make_verdict(
            verdict=NEEDS_CALLBACK,
            score=0.50,
            reasons=["Stub detector — real pipeline not yet wired"],
            processing_seconds=time.monotonic() - t0,
        )

    except Exception:
        logger.exception("analyze() caught unexpected error")
        return make_verdict(
            verdict=NEEDS_CALLBACK,
            score=None,
            reasons=[
                "Internal error during analysis",
                traceback.format_exc().splitlines()[-1],
            ],
            processing_seconds=time.monotonic() - t0,
        )
