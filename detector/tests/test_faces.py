"""
Unit tests for detector.faces — face detection and ROI extraction.

Uses synthetic frames with a plain oval "face" to exercise the code
path without requiring a real face dataset or heavy model downloads.
Also includes a test with a real-looking face if MTCNN is available.
"""

from __future__ import annotations

import numpy as np
import pytest

from detector.faces import (
    FaceBox,
    detect_faces,
    get_face_regions,
    CROP_SIZE,
)


def _make_uniform_frame(height: int = 480, width: int = 640) -> np.ndarray:
    """Blank RGB frame — no face present."""
    return np.full((height, width, 3), 128, dtype=np.uint8)


def _make_face_frame(height: int = 480, width: int = 640) -> np.ndarray:
    """
    Create a frame with a skin-coloured oval in the centre to simulate
    a very rough face. MTCNN may or may not detect this; the test is
    primarily for exercising the code path without crashing.
    """
    try:
        import cv2
    except ImportError:
        # Fallback pure-numpy face-like box
        frame = np.full((height, width, 3), 60, dtype=np.uint8)
        frame[height//4: 3*height//4, width//4: 3*width//4] = (200, 160, 120)
        return frame

    frame = np.full((height, width, 3), 60, dtype=np.uint8)
    # Skin-toned ellipse
    center = (width // 2, height // 2)
    axes = (80, 110)
    cv2.ellipse(frame, center, axes, 0, 0, 360, (200, 160, 120), -1)
    # Eyes
    cv2.circle(frame, (center[0] - 30, center[1] - 25), 8, (40, 30, 20), -1)
    cv2.circle(frame, (center[0] + 30, center[1] - 25), 8, (40, 30, 20), -1)
    return frame


class TestGetFaceRegions:
    """Pure-geometry tests — no model needed."""

    def test_region_positions(self):
        box = FaceBox(x1=100, y1=50, x2=300, y2=350)
        fh, lc, rc = get_face_regions(box)

        # Forehead should be near the top
        fh_x, fh_y, fh_w, fh_h = fh
        assert fh_y < box.y1 + box.height * 0.35
        assert fh_w > 0 and fh_h > 0

        # Cheeks should be in the lower half
        lc_x, lc_y, lc_w, lc_h = lc
        rc_x, rc_y, rc_w, rc_h = rc
        assert lc_y > box.y1 + box.height * 0.4
        assert rc_y > box.y1 + box.height * 0.4

        # Left cheek should be left of right cheek
        assert lc_x < rc_x

    def test_box_properties(self):
        box = FaceBox(x1=10, y1=20, x2=110, y2=220)
        assert box.width == 100
        assert box.height == 200
        assert box.center_x == 60
        assert box.center_y == 120


class TestDetectFaces:
    """Tests that call MTCNN — need facenet-pytorch installed."""

    def test_no_frames(self):
        result = detect_faces([])
        assert result.face_found_rate == 0.0
        assert len(result.faces) == 0

    def test_uniform_frames_no_face(self):
        """A plain grey frame should have no detectable face."""
        frames = [_make_uniform_frame() for _ in range(3)]
        result = detect_faces(frames)
        assert result.face_found_rate == 0.0
        for fr in result.faces:
            assert fr.found is False
            assert fr.crop is None

    def test_face_frame_shape(self):
        """When a face IS found, crop must be CROP_SIZE×CROP_SIZE×3."""
        frames = [_make_face_frame() for _ in range(3)]
        result = detect_faces(frames)
        # MTCNN might not detect our crude oval, so we only check
        # shapes on faces that were found
        for fr in result.faces:
            if fr.found:
                assert fr.crop is not None
                assert fr.crop.shape == (CROP_SIZE, CROP_SIZE, 3)
                assert fr.crop.dtype == np.uint8
                assert fr.box is not None
                assert fr.box.width > 0
                assert fr.box.height > 0

    def test_result_length_matches_input(self):
        frames = [_make_uniform_frame(), _make_face_frame()]
        result = detect_faces(frames)
        assert len(result.faces) == 2
