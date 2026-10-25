"""
Unit tests for detector.frames — frame extraction.

These tests use a synthetic video generated in-memory so they run
without needing any dataset downloads.
"""

from __future__ import annotations

import numpy as np
import os
import tempfile
try:
    import cv2
except ImportError:
    cv2 = None

import pytest

from detector.frames import extract_frames, MAX_DURATION, MIN_DURATION, CLASSIFIER_STEP

pytestmark = pytest.mark.skipif(cv2 is None, reason="OpenCV (cv2) is required for frame extraction tests")


def _make_test_video(
    path: str,
    fps: float = 30.0,
    duration: float = 5.0,
    width: int = 320,
    height: int = 240,
) -> str:
    """Create a short synthetic colour-cycling MP4 for testing."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    n_frames = int(fps * duration)
    for i in range(n_frames):
        # Simple colour gradient that changes each frame
        hue = int((i / n_frames) * 180)
        frame = np.full((height, width, 3), (hue, 200, 200), dtype=np.uint8)
        frame = cv2.cvtColor(frame, cv2.COLOR_HSV2BGR)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture(scope="module")
def test_video(tmp_path_factory):
    """5-second 30fps test video, shared across tests in this module."""
    d = tmp_path_factory.mktemp("videos")
    path = str(d / "test_5s.mp4")
    _make_test_video(path, fps=30.0, duration=5.0)
    return path


@pytest.fixture(scope="module")
def long_video(tmp_path_factory):
    """20-second video to test the MAX_DURATION cap."""
    d = tmp_path_factory.mktemp("videos")
    path = str(d / "test_20s.mp4")
    _make_test_video(path, fps=30.0, duration=20.0)
    return path


@pytest.fixture(scope="module")
def short_video(tmp_path_factory):
    """0.5-second video — below MIN_DURATION."""
    d = tmp_path_factory.mktemp("videos")
    path = str(d / "test_short.mp4")
    _make_test_video(path, fps=30.0, duration=0.5)
    return path


class TestExtractFrames:
    def test_basic_extraction(self, test_video):
        res = extract_frames(test_video)
        assert res.error is None
        assert res.fps == pytest.approx(30.0, abs=1.0)
        assert res.width == 320
        assert res.height == 240
        assert len(res.all_frames) == res.total_frame_count
        expected = int(5.0 * 30.0)
        assert abs(res.total_frame_count - expected) <= 2

    def test_classifier_frames_are_subsampled(self, test_video):
        res = extract_frames(test_video)
        expected_clf = len(res.all_frames) // CLASSIFIER_STEP + 1
        assert abs(len(res.classifier_frames) - expected_clf) <= 1
        for idx in res.classifier_indices:
            assert idx % CLASSIFIER_STEP == 0

    def test_frames_are_rgb(self, test_video):
        res = extract_frames(test_video)
        assert res.all_frames[0].ndim == 3
        assert res.all_frames[0].shape[2] == 3  # RGB channels

    def test_max_duration_cap(self, long_video):
        res = extract_frames(long_video)
        assert res.error is None
        max_expected = int(MAX_DURATION * 30.0)
        assert res.total_frame_count <= max_expected + 1

    def test_short_video_error(self, short_video):
        res = extract_frames(short_video)
        assert res.error is not None
        assert "too short" in res.error.lower()

    def test_nonexistent_file(self):
        res = extract_frames("/nonexistent/video.mp4")
        assert res.error is not None

    def test_empty_file(self, tmp_path):
        empty = str(tmp_path / "empty.mp4")
        with open(empty, "wb") as f:
            f.write(b"")
        res = extract_frames(empty)
        assert res.error is not None
