"""
Unit tests for detector.features — consolidated feature extraction.
"""

from __future__ import annotations

import numpy as np
import pytest

from detector.classifiers import ClassifierResult
from detector.faces import FaceBatchResult, FaceResult
from detector.features import (
    FEATURE_NAMES,
    VideoFeatures,
    extract_features,
)
from detector.frames import FrameResult
from detector.pulse import PulseResult


def test_video_features_vector():
    """Verify feature vector length, types, and ordering."""
    vf = VideoFeatures(
        face_found_rate=0.95,
        effnet_mean=0.82,
        effnet_max=0.91,
        effnet_top10=0.88,
        effnet_std=0.05,
        siglip_mean=0.75,
        siglip_max=0.85,
        siglip_top10=0.80,
        siglip_std=0.04,
        pulse_bpm=72.0,
        pulse_snr=4.5,
        pulse_bpm_plausible=1.0,
        pulse_mean_region_corr=0.85,
        pulse_screen_flicker_corr=0.20,
        pulse_is_flicker=0.0,
        pulse_signal_power=0.002,
        flagged_frames=[41, 52, 88],
    )

    vec = vf.to_vector()
    assert len(vec) == len(FEATURE_NAMES)
    assert np.all(np.isfinite(vec))

    d = vf.to_dict()
    assert d["face_found_rate"] == 0.95
    assert d["pulse_bpm"] == 72.0
    assert d["pulse_is_flicker"] == 0.0


def test_extract_features_combines_modules():
    """Test extract_features correctly combines outputs from upstream modules."""
    frame_res = FrameResult(total_frame_count=150, fps=30.0)
    face_res = FaceBatchResult(face_found_rate=0.80)
    pulse_res = PulseResult(
        bpm=68.5,
        snr=3.2,
        bpm_plausible=True,
        mean_region_corr=0.74,
        screen_flicker_corr=0.15,
        is_screen_flicker=False,
        signal_power=0.0012,
        valid=True,
    )
    clf_res = ClassifierResult(
        mean_effnet=0.65,
        max_effnet=0.88,
        top10_effnet=0.80,
        std_effnet=0.10,
        flagged_frames=[12, 14, 16],
    )

    feat = extract_features(frame_res, face_res, pulse_res, clf_res)
    assert feat.face_found_rate == 0.80
    assert feat.pulse_bpm == 68.5
    assert feat.pulse_bpm_plausible == 1.0
    assert feat.effnet_max == 0.88
    assert feat.flagged_frames == [12, 14, 16]
