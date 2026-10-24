"""
SentinelSeal Detector — Face detection and cropping.

Uses facenet-pytorch's MTCNN to find the largest face in each frame,
then produces a 224×224 crop with a small margin (matching the
EfficientNet model's expected input).

Also returns face bounding boxes for ROI extraction (pulse module).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────
CROP_SIZE = 224           # pixels — what the classifiers expect
MARGIN_FRACTION = 0.15    # enlarge the bounding box by 15% on each side


# Lazy singleton so the MTCNN model is loaded only once
_detector = None


def _get_detector():
    """Lazily load MTCNN — heavy import kept out of module top-level."""
    global _detector
    if _detector is None:
        try:
            from facenet_pytorch import MTCNN

            _detector = MTCNN(
                image_size=CROP_SIZE,
                margin=int(CROP_SIZE * MARGIN_FRACTION),
                keep_all=False,        # largest face only
                select_largest=True,
                post_process=False,    # return uint8 PIL, not normalised tensor
                device="cpu",
            )
            logger.info("MTCNN loaded (CPU)")
        except ImportError:
            logger.warning("facenet-pytorch not installed; MTCNN unavailable")
            return None
        except Exception as e:
            logger.warning(f"Failed to load MTCNN: {e}")
            return None
    return _detector


@dataclass
class FaceBox:
    """Bounding box of a detected face in pixel coords of the original frame."""
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center_x(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        return (self.y1 + self.y2) // 2


@dataclass
class FaceResult:
    """Per-frame face detection output."""
    crop: Optional[np.ndarray] = None     # 224×224 RGB uint8 or None
    box: Optional[FaceBox] = None         # bounding box in original coords
    found: bool = False


@dataclass
class FaceBatchResult:
    """Results for a batch of frames."""
    faces: List[FaceResult] = field(default_factory=list)
    face_found_rate: float = 0.0


def detect_faces(frames: List[np.ndarray]) -> FaceBatchResult:
    """
    Detect the largest face in each frame.

    Parameters
    ----------
    frames : list of np.ndarray
        RGB uint8 frames (H, W, 3).

    Returns
    -------
    FaceBatchResult
        One FaceResult per input frame, plus the overall face-found rate.
    """
    detector = _get_detector()
    if detector is None or Image is None:
        return FaceBatchResult(
            faces=[FaceResult() for _ in frames],
            face_found_rate=0.0,
        )

    results: List[FaceResult] = []
    found_count = 0

    for frame in frames:
        fr = FaceResult()
        try:
            pil_img = Image.fromarray(frame)
            boxes, probs = detector.detect(pil_img)

            if boxes is not None and len(boxes) > 0:
                # Take the first (largest) face
                box = boxes[0]
                x1, y1, x2, y2 = [int(round(v)) for v in box]
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if x2 > x1 and y2 > y1:
                    fr.box = FaceBox(x1=x1, y1=y1, x2=x2, y2=y2)
                    fr.found = True
                    found_count += 1

                    # Extract crop with margin, resize to CROP_SIZE × CROP_SIZE
                    margin_w = int((x2 - x1) * MARGIN_FRACTION)
                    margin_h = int((y2 - y1) * MARGIN_FRACTION)
                    cx1 = max(0, x1 - margin_w)
                    cy1 = max(0, y1 - margin_h)
                    cx2 = min(w, x2 + margin_w)
                    cy2 = min(h, y2 + margin_h)

                    crop = frame[cy1:cy2, cx1:cx2]
                    crop_pil = Image.fromarray(crop).resize(
                        (CROP_SIZE, CROP_SIZE), Image.BILINEAR
                    )
                    fr.crop = np.array(crop_pil)

        except Exception:
            logger.debug("Face detection failed on one frame", exc_info=True)

        results.append(fr)

    total = len(frames) if frames else 1
    return FaceBatchResult(
        faces=results,
        face_found_rate=found_count / total,
    )


def get_face_regions(
    box: FaceBox,
) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    """
    Derive forehead, left-cheek, and right-cheek ROIs from a face bounding box.

    Uses the same proportions as native-lib.cpp for the forehead
    (45% width, 20% height, 10% top offset) and adds symmetric cheek regions.

    Returns
    -------
    (forehead, left_cheek, right_cheek)
        Each is (x, y, w, h) in original-frame pixel coordinates.
    """
    bw = box.width
    bh = box.height

    # Forehead: center-ish strip near the top of the face box
    fh_w = int(bw * 0.45)
    fh_h = int(bh * 0.20)
    fh_x = box.x1 + (bw - fh_w) // 2
    fh_y = box.y1 + int(bh * 0.10)

    # Left cheek (from the subject's perspective, left side of image)
    ch_w = int(bw * 0.20)
    ch_h = int(bh * 0.20)
    lc_x = box.x1 + int(bw * 0.08)
    lc_y = box.y1 + int(bh * 0.50)

    # Right cheek
    rc_x = box.x1 + int(bw * 0.72)
    rc_y = lc_y

    return (
        (fh_x, fh_y, fh_w, fh_h),
        (lc_x, lc_y, ch_w, ch_h),
        (rc_x, rc_y, ch_w, ch_h),
    )


# ── CLI entry-point ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m detector.faces <video_path>")
        sys.exit(1)

    from detector.frames import extract_frames

    video_path = sys.argv[1]
    print(f"Extracting frames from {video_path} …")
    fr = extract_frames(video_path)

    if fr.error:
        print(f"ERROR: {fr.error}")
        sys.exit(1)

    print(f"Got {len(fr.classifier_frames)} classifier frames. Running MTCNN …")
    fb = detect_faces(fr.classifier_frames)

    print(f"\nFace-found rate: {fb.face_found_rate:.2%}")
    for i, face in enumerate(fb.faces):
        if face.found:
            bx = face.box
            regions = get_face_regions(bx)
            print(
                f"  Frame {fr.classifier_indices[i]:4d}: "
                f"box=({bx.x1},{bx.y1})→({bx.x2},{bx.y2})  "
                f"crop={face.crop.shape}"
            )
        else:
            print(f"  Frame {fr.classifier_indices[i]:4d}: no face")
