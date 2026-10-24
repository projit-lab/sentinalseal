"""
SentinelSeal Detector — Feature Extraction & Aggregation.

Combines signals from:
  1. Face detection (face-found rate, stability)
  2. Pretrained classifiers (EfficientNet-B4 & SigLIP summary statistics)
  3. rPPG pulse coherence (BPM plausibility, SNR, 3-region correlation, flicker)

Produces a standardized 1D feature vector for the fusion layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from detector.classifiers import ClassifierResult
from detector.faces import FaceBatchResult
from detector.frames import FrameResult
from detector.pulse import PulseResult

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "face_found_rate",
    "effnet_mean",
    "effnet_max",
    "effnet_top10",
    "effnet_std",
    "siglip_mean",
    "siglip_max",
    "siglip_top10",
    "siglip_std",
    "pulse_bpm",
    "pulse_snr",
    "pulse_bpm_plausible",
    "pulse_mean_region_corr",
    "pulse_screen_flicker_corr",
    "pulse_is_flicker",
    "pulse_signal_power",
]


@dataclass
class VideoFeatures:
    """Consolidated features extracted from a video clip."""
    face_found_rate: float = 0.0

    effnet_mean: float = 0.0
    effnet_max: float = 0.0
    effnet_top10: float = 0.0
    effnet_std: float = 0.0

    siglip_mean: float = 0.0
    siglip_max: float = 0.0
    siglip_top10: float = 0.0
    siglip_std: float = 0.0

    pulse_bpm: float = 0.0
    pulse_snr: float = 0.0
    pulse_bpm_plausible: float = 0.0
    pulse_mean_region_corr: float = 0.0
    pulse_screen_flicker_corr: float = 0.0
    pulse_is_flicker: float = 0.0
    pulse_signal_power: float = 0.0

    flagged_frames: List[int] = field(default_factory=list)

    def to_vector(self) -> np.ndarray:
        """Return 1D float64 numpy array matching FEATURE_NAMES order."""
        return np.array(
            [
                self.face_found_rate,
                self.effnet_mean,
                self.effnet_max,
                self.effnet_top10,
                self.effnet_std,
                self.siglip_mean,
                self.siglip_max,
                self.siglip_top10,
                self.siglip_std,
                self.pulse_bpm,
                self.pulse_snr,
                self.pulse_bpm_plausible,
                self.pulse_mean_region_corr,
                self.pulse_screen_flicker_corr,
                self.pulse_is_flicker,
                self.pulse_signal_power,
            ],
            dtype=np.float64,
        )

    def to_dict(self) -> Dict[str, float]:
        """Return dict representation."""
        vec = self.to_vector()
        return {name: float(vec[i]) for i, name in enumerate(FEATURE_NAMES)}


def extract_features(
    frame_res: FrameResult,
    face_res: FaceBatchResult,
    pulse_res: PulseResult,
    clf_res: ClassifierResult,
) -> VideoFeatures:
    """
    Consolidate all extraction results into a unified VideoFeatures instance.
    """
    feat = VideoFeatures()

    # Face detector features
    feat.face_found_rate = round(float(face_res.face_found_rate), 4)

    # Classifier features
    feat.effnet_mean = clf_res.mean_effnet
    feat.effnet_max = clf_res.max_effnet
    feat.effnet_top10 = clf_res.top10_effnet
    feat.effnet_std = clf_res.std_effnet

    feat.siglip_mean = clf_res.mean_siglip
    feat.siglip_max = clf_res.max_siglip
    feat.siglip_top10 = clf_res.top10_siglip
    feat.siglip_std = clf_res.std_siglip

    feat.flagged_frames = clf_res.flagged_frames

    # Pulse features
    if pulse_res.valid:
        feat.pulse_bpm = pulse_res.bpm
        feat.pulse_snr = pulse_res.snr
        feat.pulse_bpm_plausible = 1.0 if pulse_res.bpm_plausible else 0.0
        feat.pulse_mean_region_corr = pulse_res.mean_region_corr
        feat.pulse_screen_flicker_corr = pulse_res.screen_flicker_corr
        feat.pulse_is_flicker = 1.0 if pulse_res.is_screen_flicker else 0.0
        feat.pulse_signal_power = pulse_res.signal_power
    else:
        # Default neutral/unobserved values
        feat.pulse_bpm = 0.0
        feat.pulse_snr = 0.0
        feat.pulse_bpm_plausible = 0.0
        feat.pulse_mean_region_corr = 0.0
        feat.pulse_screen_flicker_corr = 0.0
        feat.pulse_is_flicker = 0.0
        feat.pulse_signal_power = 0.0

    return feat
