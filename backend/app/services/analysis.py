"""
Runs Part A's detector on an uploaded instruction video.

Order matters for the privacy safeguard:
  1. fingerprint the file (SHA-256)
  2. run detector.analyze(path)            (Part A, never raises)
  3. save small JPEGs of up to 4 flagged frames (original-video frame numbers)
  4. delete the raw video and record raw_clip_deleted_at
An unsigned instruction is never VERIFIED: the outcome is always a hold.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.services import payments as pay
from app.services.store import DATA_DIR, REPO_ROOT, store

logger = logging.getLogger(__name__)

FRAMES_DIR = DATA_DIR / "frames"
UPLOADS_DIR = DATA_DIR / "uploads"
MAX_THUMBNAILS = 4

# Tests replace this with a fake; in the app it is Part A's analyze().
_analyze_override: Optional[Callable[[str], Dict[str, Any]]] = None


def set_analyze_override(fn: Optional[Callable[[str], Dict[str, Any]]]) -> None:
    global _analyze_override
    _analyze_override = fn


def _detector_unavailable(err: str) -> Dict[str, Any]:
    """Honest fallback when Part A's detector can't be imported: hold for callback."""
    return {
        "verdict": "NEEDS_CALLBACK", "score": None, "signed": False,
        "reasons": ["Not sealed by any enrolled approver",
                    "Video check unavailable on this server, so it could not be analysed"],
        "flagged_frames": [], "model_version": "unavailable", "bpm": None, "pulse_snr": None,
        "region_correlation": None, "face_found_rate": 0.0, "processing_seconds": 0.0,
        "error": err,
    }


def _run_detector(path: str) -> Dict[str, Any]:
    if _analyze_override is not None:
        return _analyze_override(path)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from detector import analyze  # Part A
    except Exception as exc:  # missing dependencies, import error
        logger.exception("Detector import failed")
        return _detector_unavailable(f"{type(exc).__name__}: {exc}")
    return analyze(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_thumbnails(video: Path, payment_id: str, frame_numbers: List[int]) -> List[int]:
    """Save up to MAX_THUMBNAILS flagged frames as small JPEGs; return the frames saved."""
    if not frame_numbers:
        return []
    try:
        import cv2
    except Exception:
        logger.warning("OpenCV not installed; skipping thumbnails")
        return []
    out_dir = FRAMES_DIR / payment_id
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[int] = []
    cap = cv2.VideoCapture(str(video))
    try:
        for n in sorted(set(frame_numbers))[:MAX_THUMBNAILS]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(n))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            scale = 240 / max(w, 1)
            small = cv2.resize(frame, (240, max(1, int(h * scale))))
            cv2.imwrite(str(out_dir / f"{int(n)}.jpg"), small, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            saved.append(int(n))
    finally:
        cap.release()
    return saved


def thumbnail_path(payment_id: str, n: int) -> Path:
    return FRAMES_DIR / payment_id / f"{int(n)}.jpg"


def analyze_instruction(payment_id: str, video_path: str) -> None:
    """Background task: analyse, thumbnail, delete, store the verdict."""
    video = Path(video_path)
    started = time.perf_counter()
    try:
        digest = sha256_file(video)
        verdict = _run_detector(str(video))
        # Detection never seals; only /auth/verify can. Enforce the contract.
        verdict["signed"] = False
        if verdict.get("verdict") not in ("NEEDS_CALLBACK", "SUSPICIOUS"):
            verdict["verdict"] = "NEEDS_CALLBACK"
        # Never show server paths in reasons
        reasons = [str(r).replace(str(video), "the uploaded video").replace(str(video.parent), "")
                   for r in (verdict.get("reasons") or [])]
        if not any("enrolled approver" in r for r in reasons):
            reasons.append("Not sealed by any enrolled approver")
        verdict["reasons"] = reasons
        thumbs = save_thumbnails(video, payment_id, list(verdict.get("flagged_frames") or []))
    except Exception as exc:
        logger.exception("Analysis failed for %s", payment_id)
        digest = None
        verdict = _detector_unavailable(f"{type(exc).__name__}: {exc}")
        verdict["reasons"][1] = "The video could not be analysed"
        thumbs = []
    finally:
        try:
            if video.exists():
                os.remove(video)
        except OSError:
            logger.exception("Could not delete %s", video)

    p = store.get_payment(payment_id)
    if p is None:
        return
    p["clip_sha256"] = digest
    p["thumbnails"] = thumbs
    p["raw_clip_deleted_at"] = pay.now_iso() if not video.exists() else None
    verdict.setdefault("processing_seconds", round(time.perf_counter() - started, 2))
    if p["status"] == pay.ANALYZING:
        pay.set_held(p, verdict, actor="detector")
    else:
        # A seal arrived while analysing: the seal wins, keep the check for the record.
        p["instruction_verdict"] = verdict
        pay.add_audit(p, "detector", "instruction checked after seal", verdict["verdict"])
    pay.add_audit(p, "system", "raw video deleted" if p["raw_clip_deleted_at"] else "raw video NOT deleted")
    store.save_payment(p)
