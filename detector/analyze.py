"""
SentinelSeal Detector — analyze(path) → verdict dict.

This is the single entry-point that Part B (backend) calls.
It **never raises**: any failure returns NEEDS_CALLBACK with a reason.

Pipeline:
  1. frames.py: OpenCV VideoCapture -> all_frames + sampled classifier_frames (~4 fps)
  2. faces.py: MTCNN -> 224x224 crops + bounding boxes
  3. pulse.py: POS rPPG -> 3-region extraction, 1024-pt FFT, SNR, BPM, cross-region correlation, flicker
  4. classifiers.py: EfficientNet-B4 + SigLIP inference -> per-frame scores & flagged frames
  5. features.py: Aggregates features into unified vector
  6. fusion.py: Calibrated decision model -> SUSPICIOUS (score >= threshold) or NEEDS_CALLBACK
  7. reasons.py: Generates plain-language explanation list
  8. contract.py: Formats verdict dict conforming to CONTRACT.md
"""

from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from detector.classifiers import classify_crops
from detector.contract import (
    HIGH_THRESHOLD,
    NEEDS_CALLBACK,
    SUSPICIOUS,
    VERIFIED,
    make_verdict,
)
from detector.faces import detect_faces
from detector.features import extract_features
from detector.frames import extract_frames
from detector.fusion import get_fusion_model
from detector.pulse import analyze_pulse
from detector.reasons import generate_reasons

logger = logging.getLogger(__name__)


def analyze(path: str) -> Dict:
    """
    Analyse a video file for deepfake indicators.

    Parameters
    ----------
    path : str
        Absolute or relative path to a video file.

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
                reasons=[f"File not found: {p.name}", "Held for out-of-band callback confirmation"],
                processing_seconds=round(time.monotonic() - t0, 3),
            )

        if not p.is_file():
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[f"Path is not a file: {p.name}", "Held for callback"],
                processing_seconds=round(time.monotonic() - t0, 3),
            )

        # ── 1. Frame Extraction ──────────────────────────────────────────
        frame_res = extract_frames(str(p))
        if frame_res.error:
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[frame_res.error, "Held for callback"],
                processing_seconds=round(time.monotonic() - t0, 3),
            )

        if not frame_res.classifier_frames:
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=["No readable frames in video file", "Held for callback"],
                processing_seconds=round(time.monotonic() - t0, 3),
            )

        # ── 2. Face Detection ───────────────────────────────────────────
        face_batch = detect_faces(frame_res.classifier_frames)

        # If completely no face detected across all frames
        if face_batch.face_found_rate == 0.0:
            return make_verdict(
                face_found_rate=0.0,
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[
                    "No human face visible in video (audio-only, profile angle, or camera obstructed)",
                    "Held for out-of-band callback confirmation",
                ],
                processing_seconds=round(time.monotonic() - t0, 3),
            )

        # Gather crops and corresponding original video frame indices
        valid_crops = []
        valid_crop_indices = []
        for i, face in enumerate(face_batch.faces):
            if face.found and face.crop is not None:
                valid_crops.append(face.crop)
                valid_crop_indices.append(frame_res.classifier_indices[i])

        # Build face boxes aligned with all_frames for pulse tracking
        all_boxes: List[Optional[Tuple[int, int, int, int]]] = []
        last_box = None
        cf_idx_map = {idx: face_batch.faces[i] for i, idx in enumerate(frame_res.classifier_indices)}

        for fi in range(len(frame_res.all_frames)):
            if fi in cf_idx_map and cf_idx_map[fi].found and cf_idx_map[fi].box:
                bx = cf_idx_map[fi].box
                last_box = (bx.x1, bx.y1, bx.x2, bx.y2)
            all_boxes.append(last_box)

        # ── 3. Pulse & Cross-Region Coherence (POS) ─────────────────────
        pulse_res = analyze_pulse(frame_res.all_frames, all_boxes, fps=frame_res.fps)

        # ── 4. Deepfake Neural Classifiers ──────────────────────────────
        clf_res = classify_crops(valid_crops, valid_crop_indices)

        details = dict(
            bpm=pulse_res.bpm if pulse_res.valid else None,
            pulse_snr=pulse_res.snr if pulse_res.valid else None,
            region_correlation=pulse_res.mean_region_corr if pulse_res.valid else None,
            face_found_rate=round(face_batch.face_found_rate, 3),
        )

        if not clf_res.models_used:
            return make_verdict(
                verdict=NEEDS_CALLBACK,
                score=None,
                reasons=[
                    "Deepfake models are not loaded on this server, so the video was not checked for manipulation",
                    "Held for out-of-band callback confirmation",
                ],
                processing_seconds=round(time.monotonic() - t0, 3),
                **details,
            )

        # ── 5. Feature Extraction ───────────────────────────────────────
        features = extract_features(frame_res, face_batch, pulse_res, clf_res)

        # ── 6. Fusion Decision Layer ────────────────────────────────────
        fusion_model = get_fusion_model()
        score, verdict = fusion_model.decide(features)

        # ── 7. Plain-Language Reasons ───────────────────────────────────
        reasons = generate_reasons(
            features=features,
            frame_res=frame_res,
            face_res=face_batch,
            pulse_res=pulse_res,
            clf_res=clf_res,
            signed=False,
        )

        return make_verdict(
            verdict=verdict,
            score=score,
            reasons=reasons,
            flagged_frames=features.flagged_frames,
            signed=False,
            processing_seconds=round(time.monotonic() - t0, 3),
            **details,
        )

    except Exception:
        logger.exception("analyze() encountered an unhandled exception")
        last_err = traceback.format_exc().splitlines()[-1]
        return make_verdict(
            verdict=NEEDS_CALLBACK,
            score=None,
            reasons=[
                "Unexpected internal error during video analysis",
                last_err,
                "Held for out-of-band callback confirmation",
            ],
            processing_seconds=round(time.monotonic() - t0, 3),
        )


# ── CLI test entry-point ─────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m detector.analyze <video_path>")
        sys.exit(1)

    video_path = sys.argv[1]
    res = analyze(video_path)
    print(json.dumps(res, indent=2))
