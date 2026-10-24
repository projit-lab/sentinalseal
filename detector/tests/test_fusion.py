"""
Unit tests for detector.fusion — fusion layer and calibrated decisions.
"""

from __future__ import annotations

import numpy as np
import pytest

from detector.contract import NEEDS_CALLBACK, SUSPICIOUS, VERIFIED
from detector.features import VideoFeatures
from detector.fusion import FusionModel, get_fusion_model


def test_fusion_decision_genuine_features():
    """Clean video features should produce low fake score and NEEDS_CALLBACK (since unsigned)."""
    model = FusionModel()
    # Genuine characteristics: high pulse coherence, good SNR, low classifier scores
    features = VideoFeatures(
        face_found_rate=0.98,
        effnet_mean=0.08,
        effnet_max=0.15,
        effnet_top10=0.12,
        effnet_std=0.02,
        siglip_mean=0.10,
        siglip_max=0.18,
        siglip_top10=0.14,
        siglip_std=0.03,
        pulse_bpm=72.0,
        pulse_snr=5.2,
        pulse_bpm_plausible=1.0,
        pulse_mean_region_corr=0.88,
        pulse_screen_flicker_corr=0.10,
        pulse_is_flicker=0.0,
        pulse_signal_power=0.003,
    )

    score, verdict = model.decide(features)
    assert score < model.high_threshold
    # Remember: unsigned video is NEVER VERIFIED; genuine unsigned -> NEEDS_CALLBACK
    assert verdict == NEEDS_CALLBACK


def test_fusion_decision_deepfake_features():
    """Manipulated video features should produce high fake score and SUSPICIOUS verdict."""
    model = FusionModel()
    # Deepfake characteristics: high classifier score, no pulse coherence, artifacts
    features = VideoFeatures(
        face_found_rate=0.92,
        effnet_mean=0.78,
        effnet_max=0.94,
        effnet_top10=0.90,
        effnet_std=0.08,
        siglip_mean=0.82,
        siglip_max=0.96,
        siglip_top10=0.91,
        siglip_std=0.06,
        pulse_bpm=0.0,
        pulse_snr=0.8,
        pulse_bpm_plausible=0.0,
        pulse_mean_region_corr=-0.15,
        pulse_screen_flicker_corr=0.10,
        pulse_is_flicker=0.0,
        pulse_signal_power=0.0001,
        flagged_frames=[41, 52, 88],
    )

    score, verdict = model.decide(features)
    assert score >= model.high_threshold
    assert verdict == SUSPICIOUS


def test_fusion_decision_screen_replay():
    """Screen replay (flicker) should be penalized and trigger SUSPICIOUS."""
    model = FusionModel()
    features = VideoFeatures(
        face_found_rate=0.90,
        effnet_mean=0.55,
        effnet_max=0.68,
        pulse_bpm=0.0,
        pulse_snr=1.0,
        pulse_bpm_plausible=0.0,
        pulse_mean_region_corr=0.10,
        pulse_screen_flicker_corr=0.99,
        pulse_is_flicker=1.0,
        pulse_signal_power=0.0002,
    )

    score, verdict = model.decide(features)
    assert verdict == SUSPICIOUS
