"""
SentinelSeal Detector — Plain-Language Reason Generation.

Translates numeric pipeline features into clear, human-understandable explanations
for bank checkers and fraud operations analysts.
"""

from __future__ import annotations

from typing import List

from detector.classifiers import ClassifierResult
from detector.contract import NEEDS_CALLBACK, SUSPICIOUS, VERIFIED
from detector.faces import FaceBatchResult
from detector.features import VideoFeatures
from detector.frames import FrameResult
from detector.pulse import PulseResult


def format_frame_ranges(frame_indices: List[int]) -> str:
    """Format frame numbers into concise ranges, e.g. [41, 42, 43, 88] -> '41–43, 88'."""
    if not frame_indices:
        return ""
    sorted_frames = sorted(set(frame_indices))
    ranges = []
    start = sorted_frames[0]
    prev = sorted_frames[0]

    for f in sorted_frames[1:]:
        if f == prev + 1:
            prev = f
        else:
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}–{prev}")
            start = f
            prev = f

    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}–{prev}")

    return ", ".join(ranges)


def generate_reasons(
    features: VideoFeatures,
    frame_res: Optional[FrameResult] = None,
    face_res: Optional[FaceBatchResult] = None,
    pulse_res: Optional[PulseResult] = None,
    clf_res: Optional[ClassifierResult] = None,
    signed: bool = False,
    error: Optional[str] = None,
) -> List[str]:
    """
    Generate plain-language explanations justifying the verdict.

    Parameters
    ----------
    features : VideoFeatures
        Consolidated feature vector.
    signed : bool
        Whether a valid signature from an enrolled approver was provided.
    error : Optional[str]
        Pre-pipeline error (e.g. corrupt video, no frames).
    """
    reasons: List[str] = []

    # 1. Structural / input failures
    if error:
        reasons.append(f"Input issue: {error}")
        reasons.append("Held for out-of-band callback confirmation")
        return reasons

    # 2. Cryptographic signature status
    if not signed:
        reasons.append("Not signed by any enrolled approver")

    # 3. Face visibility
    if features.face_found_rate < 0.5:
        pct_missing = int(round((1.0 - features.face_found_rate) * 100))
        reasons.append(f"No face visible for {pct_missing}% of the clip")

    # 4. Neural classifier findings
    if features.flagged_frames:
        ranges_str = format_frame_ranges(features.flagged_frames)
        reasons.append(f"Face texture inconsistent in frames {ranges_str}")
    elif max(features.effnet_max, features.siglip_max) > 0.60:
        reasons.append("Deepfake classifier detected suspicious facial manipulation artifacts")

    # 5. Physiological pulse & coherence findings
    if features.pulse_is_flicker > 0.5:
        reasons.append(
            f"Screen replay detected: optical flicker between color channels (r={features.pulse_screen_flicker_corr:.2f})"
        )
    # Pulse-based reasons are not shown to users yet: on genuine phone videos the
    # forehead/cheek agreement measured 0.00-0.35, so "no consistent pulse" accused real
    # people. The pulse values stay visible to fraud ops; reasons return once
    # eval/evaluate.py shows the pulse features separate real from fake.

    # 6. Fallback if clean but unsigned
    if len(reasons) == 1 and not signed:
        reasons.append("Visual forensics clean; held for approver callback confirmation as standard protocol")

    return reasons
