"""
Unit tests for detector.reasons — explanation generation.
"""

from __future__ import annotations

import pytest

from detector.features import VideoFeatures
from detector.reasons import format_frame_ranges, generate_reasons


def test_format_frame_ranges():
    """Verify frame index formatting into ranges."""
    assert format_frame_ranges([]) == ""
    assert format_frame_ranges([41]) == "41"
    assert format_frame_ranges([41, 42, 43]) == "41–43"
    assert format_frame_ranges([41, 42, 43, 88]) == "41–43, 88"
    assert format_frame_ranges([1, 2, 5, 7, 8, 9]) == "1–2, 5, 7–9"


def test_generate_reasons_unsupported_or_error():
    """Input errors should yield clear callback instructions."""
    vf = VideoFeatures()
    reasons = generate_reasons(vf, error="Video file corrupt", signed=False)
    assert any("Input issue: Video file corrupt" in r for r in reasons)
    assert any("callback" in r.lower() for r in reasons)


def test_generate_reasons_deepfake_evidence():
    """Reasons mention flagged frames; unvalidated pulse findings are not shown to users."""
    vf = VideoFeatures(
        face_found_rate=0.90,
        effnet_max=0.92,
        siglip_max=0.95,
        flagged_frames=[41, 42, 43, 88],
        pulse_mean_region_corr=-0.10,
        pulse_snr=1.2,
    )
    reasons = generate_reasons(vf, signed=False)

    assert any("41–43, 88" in r for r in reasons)
    assert not any("pulse" in r.lower() for r in reasons)
    assert any("Not signed by any enrolled approver" in r for r in reasons)


def test_generate_reasons_screen_flicker():
    """Screen replay reasons should mention screen flicker."""
    vf = VideoFeatures(
        face_found_rate=0.95,
        pulse_is_flicker=1.0,
        pulse_screen_flicker_corr=0.99,
    )
    reasons = generate_reasons(vf, signed=False)
    assert any("Screen replay detected" in r for r in reasons)
