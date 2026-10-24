"""
SentinelSeal Detector — Fusion Layer & Verdict Classification.

Combines classifier scores and physiological pulse signals using
StandardScaler + LogisticRegression(class_weight="balanced").

Decision rules (per FINALE_PLAN):
  - Calibrated score in [0.0, 1.0] representing fake probability.
  - If score >= HIGH_THRESHOLD (calibrated to ~5% FPR on genuine data):
      VERDICT = SUSPICIOUS
  - Otherwise:
      VERDICT = NEEDS_CALLBACK
  - Note: Unsigned videos are NEVER given VERIFIED by the detector.
    The detector determines the risk tier (SUSPICIOUS vs NEEDS_CALLBACK).
    Cryptographic verification from an enrolled phone is required for VERIFIED.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from detector.contract import NEEDS_CALLBACK, SUSPICIOUS, VERIFIED
from detector.features import FEATURE_NAMES, VideoFeatures

logger = logging.getLogger(__name__)

# Default model save path
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "weights"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "fusion_model.joblib"

# Default high threshold corresponding to ~5% FPR on genuine fit samples
DEFAULT_HIGH_THRESHOLD = 0.65


class FusionModel:
    """StandardScaler + LogisticRegression fusion pipeline."""

    def __init__(self, high_threshold: float = DEFAULT_HIGH_THRESHOLD):
        self.scaler = None
        self.classifier = None
        self.high_threshold = high_threshold
        self.feature_names = FEATURE_NAMES

    def fit(self, X: np.ndarray, y: np.ndarray, target_fpr: float = 0.05):
        """
        Fit StandardScaler and LogisticRegression on training split only.
        Calibrates high_threshold so that FPR on genuine (y == 0) is ~target_fpr.
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            logger.error("scikit-learn required to train fusion model")
            return self

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.classifier = LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)
        self.classifier.fit(X_scaled, y)

        # Calibrate threshold on genuine samples (y == 0)
        genuine_mask = (y == 0)
        if np.sum(genuine_mask) > 5:
            genuine_scores = self.classifier.predict_proba(X_scaled[genuine_mask])[:, 1]
            # 95th percentile of genuine scores gives ~5% FPR
            pct = 100.0 * (1.0 - target_fpr)
            self.high_threshold = float(np.percentile(genuine_scores, pct))
            logger.info(f"Calibrated fusion high_threshold: {self.high_threshold:.4f} for target FPR {target_fpr}")
        else:
            self.high_threshold = DEFAULT_HIGH_THRESHOLD

        return self

    def predict_score(self, features: VideoFeatures) -> float:
        """
        Predict calibrated fake probability [0.0, 1.0].
        Uses trained model if available; otherwise uses analytical rule-based fusion.
        """
        vec = features.to_vector().reshape(1, -1)

        if self.scaler is not None and self.classifier is not None:
            try:
                x_scaled = self.scaler.transform(vec)
                prob = self.classifier.predict_proba(x_scaled)[0, 1]
                return float(np.clip(prob, 0.0, 1.0))
            except Exception as e:
                logger.warning(f"Sklearn prediction failed, using fallback: {e}")

        # Fallback calibrated linear heuristic when trained weights file is not loaded
        # Emphasizes classifier worst-case + lack of biological pulse coherence
        clf_signal = 0.5 * features.effnet_max + 0.5 * features.siglip_max
        if clf_signal == 0.0:
            clf_signal = max(features.effnet_mean, features.siglip_mean)

        pulse_penalty = 0.0
        # If pulse was observed but desynchronized or low SNR or screen flicker
        if features.pulse_is_flicker > 0.5:
            pulse_penalty += 0.25
        elif features.pulse_snr < 2.0 and features.face_found_rate > 0.5:
            pulse_penalty += 0.15

        if features.pulse_mean_region_corr < 0.2 and features.face_found_rate > 0.5:
            pulse_penalty += 0.15
        elif features.pulse_mean_region_corr > 0.7 and features.pulse_bpm_plausible > 0.5:
            # Genuine skin pulse detected across forehead and cheeks
            pulse_penalty -= 0.20

        # Face visibility penalty
        if features.face_found_rate < 0.4:
            pulse_penalty += 0.10

        fused_score = float(np.clip(clf_signal + pulse_penalty, 0.0, 1.0))
        return round(fused_score, 4)

    def decide(self, features: VideoFeatures) -> Tuple[float, str]:
        """
        Determine score and verdict.
        Returns:
          (score, "SUSPICIOUS" | "NEEDS_CALLBACK")
        """
        score = self.predict_score(features)
        if score >= self.high_threshold:
            verdict = SUSPICIOUS
        else:
            verdict = NEEDS_CALLBACK
        return score, verdict

    def save(self, path: Optional[Path] = None):
        """Save fitted model to disk."""
        target = path or DEFAULT_MODEL_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            import joblib
            joblib.dump(
                {
                    "scaler": self.scaler,
                    "classifier": self.classifier,
                    "high_threshold": self.high_threshold,
                    "feature_names": self.feature_names,
                },
                target,
            )
            logger.info(f"Saved fusion model to {target}")
        except Exception as e:
            logger.warning(f"Could not save fusion model: {e}")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> FusionModel:
        """Load model from disk or return default initialized instance."""
        target = path or DEFAULT_MODEL_PATH
        model = cls()
        if target.exists():
            try:
                import joblib
                data = joblib.load(target)
                model.scaler = data.get("scaler")
                model.classifier = data.get("classifier")
                model.high_threshold = data.get("high_threshold", DEFAULT_HIGH_THRESHOLD)
                model.feature_names = data.get("feature_names", FEATURE_NAMES)
                logger.info(f"Loaded fusion model from {target}")
            except Exception as e:
                logger.warning(f"Could not load fusion model from {target}: {e}")
        return model


# Singleton instance
_fusion_singleton: Optional[FusionModel] = None


def get_fusion_model() -> FusionModel:
    global _fusion_singleton
    if _fusion_singleton is None:
        _fusion_singleton = FusionModel.load()
    return _fusion_singleton
