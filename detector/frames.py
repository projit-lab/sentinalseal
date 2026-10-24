"""
SentinelSeal Detector — Video frame extraction.

Reads up to MAX_DURATION seconds of a video.
Returns:
  - all_frames: every frame (for pulse analysis)
  - classifier_frames: every CLASSIFIER_STEP-th frame (~4 fps) for the classifiers
  - fps: original video frame rate
  - frame_indices: 0-indexed positions of the classifier frames in the full sequence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np

logger = logging.getLogger(__name__)

# ── Configurable constants ──────────────────────────────────────────
MAX_DURATION = 15.0          # seconds — cap to keep latency bounded
MIN_DURATION = 2.0           # seconds — too short for any useful analysis
CLASSIFIER_STEP = 7          # keep every 7th frame ≈ 4 fps at 30 fps source


@dataclass
class FrameResult:
    """Container for extracted frames and metadata."""
    all_frames: List[np.ndarray] = field(default_factory=list)
    classifier_frames: List[np.ndarray] = field(default_factory=list)
    classifier_indices: List[int] = field(default_factory=list)
    fps: float = 0.0
    width: int = 0
    height: int = 0
    total_frame_count: int = 0
    error: Optional[str] = None


def extract_frames(path: str) -> FrameResult:
    """
    Open a video file, read up to MAX_DURATION seconds, and return both
    the full-rate frames (for pulse) and sampled frames (for classifiers).

    Never raises — returns a FrameResult with ``error`` set on failure.
    """
    result = FrameResult()

    if cv2 is None:
        result.error = "OpenCV (cv2) is not installed"
        return result

    try:
        cap = cv2.VideoCapture(path)
    except Exception as exc:
        result.error = f"Cannot open video: {exc}"
        return result

    if not cap.isOpened():
        result.error = f"OpenCV cannot open file: {path}"
        return result

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # fallback assumption
        result.fps = fps
        result.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        result.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        max_frames = int(MAX_DURATION * fps)
        idx = 0

        while idx < max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR → RGB once, keep as uint8
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result.all_frames.append(frame_rgb)

            if idx % CLASSIFIER_STEP == 0:
                result.classifier_frames.append(frame_rgb)
                result.classifier_indices.append(idx)

            idx += 1

        result.total_frame_count = idx

        if idx == 0:
            result.error = "Video contains no readable frames (audio-only or corrupt)"
        elif idx / fps < MIN_DURATION:
            result.error = f"Video too short ({idx / fps:.1f}s, need ≥{MIN_DURATION}s)"

    finally:
        cap.release()

    return result


# ── CLI entry-point ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m detector.frames <video_path>")
        sys.exit(1)

    video_path = sys.argv[1]
    res = extract_frames(video_path)

    if res.error:
        print(f"ERROR: {res.error}")
        sys.exit(1)

    print(f"Video: {video_path}")
    print(f"  FPS:              {res.fps:.1f}")
    print(f"  Resolution:       {res.width}×{res.height}")
    print(f"  Total frames:     {res.total_frame_count}")
    print(f"  All frames kept:  {len(res.all_frames)}")
    print(f"  Classifier frames:{len(res.classifier_frames)} (every {CLASSIFIER_STEP}th)")
    print(f"  Duration:         {res.total_frame_count / res.fps:.2f}s (capped at {MAX_DURATION}s)")
