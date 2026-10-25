"""
SentinelSeal Detector — Pretrained Deepfake Classifiers.

Supports:
  1. EfficientNet-B4 (honi05/deepfake-detection, best_model.pt)
  2. SigLIP (prithivMLmods/Deep-Fake-Detector-Model)

Features per model:
  - Per-frame fake probability
  - Mean, max, top-10% (worst-case), and temporal standard deviation
  - Flagged frame indices where fake score exceeds alert threshold

Graceful degradation:
  - If weights are not yet cached or offline, models provide clear status and fallback.
  - Can run on CPU with singletons loaded once at startup.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Alert threshold for flagging an individual frame in the UI
FRAME_FLAG_THRESHOLD = 0.65

# ImageNet normalization stats
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class ClassifierResult:
    """Output metrics from image classifiers on extracted face crops."""
    effnet_scores: List[float] = field(default_factory=list)
    siglip_scores: List[float] = field(default_factory=list)

    mean_effnet: float = 0.0
    max_effnet: float = 0.0
    top10_effnet: float = 0.0
    std_effnet: float = 0.0

    mean_siglip: float = 0.0
    max_siglip: float = 0.0
    top10_siglip: float = 0.0
    std_siglip: float = 0.0

    ensemble_mean: float = 0.0
    ensemble_max: float = 0.0

    flagged_frames: List[int] = field(default_factory=list)
    models_used: List[str] = field(default_factory=list)
    valid: bool = False
    error: Optional[str] = None


class EfficientNetB4Detector:
    """
    Wrapper for honi05/deepfake-detection (EfficientNet-B4).
    """

    def __init__(self):
        self.model = None
        self.device = "cpu"
        self._load_attempted = False

    def load(self) -> bool:
        """Load weights from local cache or Hugging Face Hub."""
        if self.model is not None:
            return True
        if self._load_attempted:
            return False

        self._load_attempted = True
        try:
            import torch
            import torch.nn as nn
            from torchvision import models

            # Try to fetch or check cached checkpoint
            checkpoint_path = None
            try:
                from huggingface_hub import hf_hub_download
                checkpoint_path = hf_hub_download(
                    repo_id="honi05/deepfake-detection",
                    filename="best_model.pt",
                    local_files_only=False,
                )
            except Exception as e:
                logger.warning(f"Could not download honi05 weights: {e}")

            if not checkpoint_path or not os.path.exists(checkpoint_path):
                # Without the fine-tuned checkpoint the final layer would be random,
                # so the scores would be meaningless. Refuse instead of guessing.
                logger.warning("EfficientNet-B4 not used: deepfake checkpoint unavailable")
                return False

            # Architecture only; all weights come from the checkpoint below.
            # Head copied from the checkpoint author's code (Honi05/DeepFakeDetector,
            # src/model.py, DeepfakeClassifier): Dropout-Linear(1792,256)-ReLU-Dropout-Linear(256,1),
            # raw logit -> sigmoid at inference.
            base_model = models.efficientnet_b4(weights=None)
            in_features = base_model.classifier[1].in_features  # 1792
            base_model.classifier = nn.Sequential(
                nn.Dropout(p=0.4),
                nn.Linear(in_features, 256),
                nn.ReLU(),
                nn.Dropout(p=0.2),
                nn.Linear(256, 1),
            )

            if checkpoint_path and os.path.exists(checkpoint_path):
                state_dict = torch.load(checkpoint_path, map_location="cpu")
                # Handle possible key naming variations
                if "model_state_dict" in state_dict:
                    state_dict = state_dict["model_state_dict"]
                elif "state_dict" in state_dict:
                    state_dict = state_dict["state_dict"]

                # Strip common wrapper prefixes, then require the weights to actually fit
                for prefix in ("module.", "model.", "backbone.", "net."):
                    if state_dict and all(k.startswith(prefix) for k in state_dict):
                        state_dict = {k[len(prefix):]: v for k, v in state_dict.items()}
                try:
                    res = base_model.load_state_dict(state_dict, strict=False)
                except Exception as e:
                    logger.warning(f"EfficientNet-B4 not used: checkpoint does not fit ({e})")
                    return False
                expected = len(base_model.state_dict())
                if any(k.startswith("classifier") for k in res.missing_keys) or len(res.missing_keys) > 0.05 * expected:
                    logger.warning(
                        "EfficientNet-B4 not used: checkpoint keys do not match "
                        f"({len(res.missing_keys)} of {expected} weights missing, e.g. {res.missing_keys[:3]})")
                    return False
                logger.info("Loaded honi05/deepfake-detection weights (%d missing, %d unexpected)",
                            len(res.missing_keys), len(res.unexpected_keys))

            base_model.eval()
            self.model = base_model
            return True
        except Exception as exc:
            logger.warning(f"Failed to initialize EfficientNet-B4: {exc}")
            return False

    def predict_crops(self, crops: List[np.ndarray]) -> List[float]:
        """
        Run inference on a batch of 224x224 RGB uint8 numpy images.
        Returns list of fake probabilities [0.0, 1.0].
        """
        if not self.load() or not crops:
            return []

        import torch

        # Preprocess: float32, [0, 1], ImageNet normalized, (B, C, H, W)
        tensors = []
        for crop in crops:
            img = crop.astype(np.float32) / 255.0
            norm = (img - IMAGENET_MEAN) / IMAGENET_STD
            t = torch.from_numpy(norm.transpose(2, 0, 1)).float()
            tensors.append(t)

        batch = torch.stack(tensors, dim=0)

        with torch.no_grad():
            logits = self.model(batch)
            if logits.shape[1] == 1:
                probs = torch.sigmoid(logits).squeeze(1).tolist()
            else:
                probs = torch.softmax(logits, dim=1)[:, 1].tolist()

        if isinstance(probs, float):
            probs = [probs]
        return [float(p) for p in probs]


class SigLIPDetector:
    """
    Wrapper for prithivMLmods/Deep-Fake-Detector-Model (SigLIP / ViT).
    """

    def __init__(self):
        self.pipe = None
        self._load_attempted = False

    def load(self) -> bool:
        if self.pipe is not None:
            return True
        if self._load_attempted:
            return False

        self._load_attempted = True
        try:
            from transformers import pipeline

            self.pipe = pipeline(
                "image-classification",
                model="prithivMLmods/Deep-Fake-Detector-Model",
                device=-1,  # CPU
            )
            logger.info("Loaded prithivMLmods/Deep-Fake-Detector-Model (SigLIP)")
            return True
        except Exception as exc:
            logger.warning(f"SigLIP pipeline load failed: {exc}")
            return False

    def predict_crops(self, crops: List[np.ndarray]) -> List[float]:
        """Run classification on crops."""
        if not self.load() or not crops:
            return []

        from PIL import Image

        scores = []
        for crop in crops:
            try:
                pil_img = Image.fromarray(crop)
                outputs = self.pipe(pil_img)
                # Parse output labels (e.g., 'fake', 'deepfake', 'artificial' vs 'real')
                fake_prob = 0.0
                for item in outputs:
                    label = item.get("label", "").lower()
                    if any(k in label for k in ["fake", "synthetic", "manipulated", "artificial"]):
                        fake_prob = float(item.get("score", 0.0))
                        break
                    elif any(k in label for k in ["real", "genuine", "authentic"]):
                        fake_prob = 1.0 - float(item.get("score", 0.0))
                scores.append(fake_prob)
            except Exception as e:
                logger.debug(f"SigLIP inference error on frame: {e}")

        return scores


# Lazy singletons
_effnet_singleton: Optional[EfficientNetB4Detector] = None
_siglip_singleton: Optional[SigLIPDetector] = None


def get_effnet_detector() -> EfficientNetB4Detector:
    global _effnet_singleton
    if _effnet_singleton is None:
        _effnet_singleton = EfficientNetB4Detector()
    return _effnet_singleton


def get_siglip_detector() -> SigLIPDetector:
    global _siglip_singleton
    if _siglip_singleton is None:
        _siglip_singleton = SigLIPDetector()
    return _siglip_singleton


def compute_score_stats(scores: List[float]) -> Tuple[float, float, float, float]:
    """Calculate (mean, max, top-10% worst-case mean, standard deviation)."""
    if not scores:
        return 0.0, 0.0, 0.0, 0.0

    arr = np.array(scores, dtype=np.float64)
    mean_val = float(np.mean(arr))
    max_val = float(np.max(arr))
    std_val = float(np.std(arr))

    # Top 10% worst frames (highest fake scores)
    k = max(1, int(np.ceil(0.10 * len(arr))))
    top_k = np.sort(arr)[-k:]
    top10_val = float(np.mean(top_k))

    return round(mean_val, 4), round(max_val, 4), round(top10_val, 4), round(std_val, 4)


def classify_crops(
    crops: List[np.ndarray],
    frame_indices: List[int],
) -> ClassifierResult:
    """
    Run the classifier ensemble on detected face crops.

    Parameters
    ----------
    crops : List[np.ndarray]
        224x224 RGB uint8 face crops.
    frame_indices : List[int]
        Frame index in original video corresponding to each crop.

    Returns
    -------
    ClassifierResult
        Per-model and fused summary metrics + flagged frame indices.
    """
    result = ClassifierResult()

    if not crops:
        result.error = "No face crops provided for classification"
        return result

    effnet = get_effnet_detector()
    siglip = get_siglip_detector()

    # Run EfficientNet
    eff_scores = effnet.predict_crops(crops)
    if eff_scores:
        result.effnet_scores = eff_scores
        result.models_used.append("EfficientNet-B4 (honi05)")
        m, mx, t10, s = compute_score_stats(eff_scores)
        result.mean_effnet = m
        result.max_effnet = mx
        result.top10_effnet = t10
        result.std_effnet = s

    # Run SigLIP
    sig_scores = siglip.predict_crops(crops)
    if sig_scores:
        result.siglip_scores = sig_scores
        result.models_used.append("SigLIP (prithivMLmods)")
        m, mx, t10, s = compute_score_stats(sig_scores)
        result.mean_siglip = m
        result.max_siglip = mx
        result.top10_siglip = t10
        result.std_siglip = s

    # If neither model was available (e.g. offline/weights not present), synthesize baseline
    if not result.models_used:
        result.valid = False
        result.error = "No pretrained classifier models could be loaded"
        return result

    # Compute combined ensemble scores
    all_means = []
    all_maxes = []
    if eff_scores:
        all_means.append(result.mean_effnet)
        all_maxes.append(result.max_effnet)
    if sig_scores:
        all_means.append(result.mean_siglip)
        all_maxes.append(result.max_siglip)

    result.ensemble_mean = round(float(np.mean(all_means)), 4)
    result.ensemble_max = round(float(np.max(all_maxes)), 4)

    # Flag frames exceeding threshold
    flagged = set()
    for i, idx in enumerate(frame_indices):
        e_s = eff_scores[i] if i < len(eff_scores) else 0.0
        s_s = sig_scores[i] if i < len(sig_scores) else 0.0
        frame_score = max(e_s, s_s)
        if frame_score >= FRAME_FLAG_THRESHOLD:
            flagged.add(idx)

    result.flagged_frames = sorted(list(flagged))
    result.valid = True
    return result
