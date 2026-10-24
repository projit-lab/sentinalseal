"""
SentinelSeal Detector — verdict constants and type hints.
"""

from __future__ import annotations

from typing import List, Optional

# ── Verdict constants ───────────────────────────────────────────────
VERIFIED = "VERIFIED"
NEEDS_CALLBACK = "NEEDS_CALLBACK"
SUSPICIOUS = "SUSPICIOUS"

# ── High threshold (score >= this → SUSPICIOUS) ─────────────────────
HIGH_THRESHOLD = 0.65

# ── Model version tag ───────────────────────────────────────────────
MODEL_VERSION = "fusion-v1"


def make_verdict(
    *,
    verdict: str,
    score: Optional[float],
    signed: bool = False,
    reasons: List[str],
    flagged_frames: Optional[List[int]] = None,
    bpm: Optional[float] = None,
    pulse_snr: Optional[float] = None,
    region_correlation: Optional[float] = None,
    face_found_rate: float = 0.0,
    processing_seconds: float = 0.0,
) -> dict:
    """Build a verdict dict matching the CONTRACT.md schema."""
    return {
        "verdict": verdict,
        "score": score,
        "signed": signed,
        "reasons": list(reasons),
        "flagged_frames": flagged_frames or [],
        "model_version": MODEL_VERSION,
        "bpm": bpm,
        "pulse_snr": pulse_snr,
        "region_correlation": region_correlation,
        "face_found_rate": face_found_rate,
        "processing_seconds": processing_seconds,
    }
