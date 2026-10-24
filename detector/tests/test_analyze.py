"""
Unit tests for detector.analyze — the main entry point.

Tests the stub behaviour and the never-raise contract.
"""

from __future__ import annotations

import tempfile
import os
import pytest

from detector.analyze import analyze
from detector.contract import NEEDS_CALLBACK


class TestAnalyzeContract:
    def test_nonexistent_file_returns_needs_callback(self):
        result = analyze("/nonexistent/path/video.mp4")
        assert result["verdict"] == NEEDS_CALLBACK
        assert "not found" in result["reasons"][0].lower() or "File not found" in result["reasons"][0]

    def test_directory_returns_needs_callback(self, tmp_path):
        result = analyze(str(tmp_path))
        assert result["verdict"] == NEEDS_CALLBACK
        assert "not a file" in result["reasons"][0].lower()

    def test_existing_file_returns_dict(self, tmp_path):
        video = tmp_path / "fake.mp4"
        video.write_bytes(b"\x00" * 100)
        result = analyze(str(video))
        assert isinstance(result, dict)
        assert "verdict" in result
        assert "score" in result
        assert "reasons" in result
        assert isinstance(result["reasons"], list)
        assert "model_version" in result
        assert "processing_seconds" in result

    def test_never_raises(self):
        """Even bizarre input must not raise."""
        result = analyze("")
        assert isinstance(result, dict)
        assert result["verdict"] == NEEDS_CALLBACK

    def test_required_fields_present(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"\x00" * 100)
        result = analyze(str(video))
        required = [
            "verdict", "score", "signed", "reasons", "flagged_frames",
            "model_version", "bpm", "pulse_snr", "region_correlation",
            "face_found_rate", "processing_seconds",
        ]
        for field in required:
            assert field in result, f"Missing field: {field}"
