"""
SentinelSeal Detector — Pulse extraction and cross-region coherence.

Direct Python port of the POS (Plane-Orthogonal-to-Skin) rPPG algorithm from
app/src/main/cpp/native-lib.cpp, extended with:
  1. Multi-region extraction (forehead, left cheek, right cheek)
  2. Cross-region pulse correlation (real faces pulse coherently across regions;
     deepfakes and face-swaps exhibit desynchronized or absent pulsatile signals)
  3. Screen-flicker / replay detection via green-red correlation
  4. Spectral SNR and BPM estimation via 1024-point FFT with quadratic sub-bin interpolation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Algorithm Constants (matched to native-lib.cpp & FINALE_PLAN) ───────
TARGET_FS = 30.0              # Hz: uniform resample rate
WINDOW_SECONDS = 5.0          # seconds: temporal window for POS analysis
MIN_FRAMES_REQUIRED = 45      # at least ~1.5 s of face data needed
FFT_SIZE = 1024               # zero-padded FFT resolution (~0.0293 Hz/bin)

# Cardiac band: 0.70 Hz (42 BPM) to 4.0 Hz (240 BPM)
MIN_BPM = 42.0
MAX_BPM = 240.0
FREQ_MIN = MIN_BPM / 60.0     # 0.70 Hz
FREQ_MAX = MAX_BPM / 60.0     # 4.00 Hz

# Screen flicker threshold from native-lib.cpp L228
FLICKER_CORR_THRESHOLD = 0.98
# Disabled for uploaded videos: on real phone recordings of a live face the green-red
# correlation is ~0.99 (lighting and motion move all channels together), so this check
# flagged genuine videos as "screen replay". Re-enable only after validating it on data.
FLICKER_CHECK_ENABLED = False


@dataclass
class PulseResult:
    """Pulse extraction and coherence metrics."""
    bpm: float = 0.0
    snr: float = 0.0                     # peak-to-noise ratio in cardiac band
    bpm_plausible: bool = False          # true if BPM within normal human range [45, 180] and SNR >= 2.0
    region_correlations: Dict[str, float] = field(default_factory=dict)
    mean_region_corr: float = 0.0        # mean correlation between forehead, left, right cheek
    screen_flicker_corr: float = 0.0     # green-red Pearson correlation
    is_screen_flicker: bool = False      # true if green-red r > 0.98 (screen replay attack)
    signal_power: float = 0.0            # RMS power of detrended pulse signal
    valid: bool = False
    error: Optional[str] = None


def extract_pos_pulse(
    r_signal: np.ndarray,
    g_signal: np.ndarray,
    b_signal: np.ndarray,
) -> np.ndarray:
    """
    Core POS (Plane-Orthogonal-to-Skin) algorithm from native-lib.cpp L170–198.

    Wang et al., "Algorithmic Principles of Remote PPG", IEEE TBME 2017.
    """
    n = len(r_signal)
    if n == 0:
        return np.array([], dtype=np.float64)

    mean_r = np.mean(r_signal)
    mean_g = np.mean(g_signal)
    mean_b = np.mean(b_signal)

    # Normalize by temporal mean
    norm_r = r_signal / (mean_r + 1e-6)
    norm_g = g_signal / (mean_g + 1e-6)
    norm_b = b_signal / (mean_b + 1e-6)

    # Two orthogonal projection axes
    x = norm_g - norm_b
    y = norm_g + norm_b - (2.0 * norm_r)

    std_x = np.std(x)
    std_y = np.std(y)

    alpha = std_x / (std_y + 1e-6)
    pulse = x + (alpha * y)
    return pulse


def apply_fir_detrending(signal: np.ndarray, window_size: int = 30) -> np.ndarray:
    """
    Moving-average subtraction (zero-phase FIR high-pass detrending).
    Matches native-lib.cpp L69–94.
    """
    n = len(signal)
    if n == 0:
        return np.array([], dtype=np.float64)

    # Centered moving average
    half = window_size // 2
    detrended = np.zeros(n, dtype=np.float64)

    for i in range(n):
        start_idx = max(0, i - half)
        end_idx = min(n, i + half + 1)
        local_mean = np.mean(signal[start_idx:end_idx])
        detrended[i] = signal[i] - local_mean

    return detrended


def resample_signals(
    signals: np.ndarray,
    source_fps: float,
    target_fs: float = TARGET_FS,
) -> np.ndarray:
    """
    Resample time series (N, channels) to uniform target_fs grid.
    """
    n = len(signals)
    if n < 2 or abs(source_fps - target_fs) < 0.1:
        return signals

    duration = n / source_fps
    t_orig = np.linspace(0, duration, n, endpoint=False)
    target_n = int(round(duration * target_fs))
    if target_n < 2:
        return signals

    t_new = np.linspace(0, duration, target_n, endpoint=False)

    if signals.ndim == 1:
        return np.interp(t_new, t_orig, signals)

    resampled = np.zeros((target_n, signals.shape[1]), dtype=np.float64)
    for c in range(signals.shape[1]):
        resampled[:, c] = np.interp(t_new, t_orig, signals[:, c])
    return resampled


def compute_spectral_bpm_and_snr(
    signal: np.ndarray,
    fs: float = TARGET_FS,
    fft_size: int = FFT_SIZE,
) -> Tuple[float, float, float]:
    """
    FFT spectral analysis with Hamming window, zero padding, and quadratic sub-bin interpolation.
    Matches native-lib.cpp L253–327.

    Returns:
      (bpm, snr, signal_power)
    """
    n = len(signal)
    if n < 30:
        return 0.0, 0.0, 0.0

    # Hamming window
    hamming = 0.54 - 0.46 * np.cos(2.0 * np.pi * np.arange(n) / (n - 1))
    windowed = signal * hamming

    # Signal power (RMS)
    signal_power = float(np.sqrt(np.mean(windowed ** 2)))
    if signal_power < 1e-5:
        return 0.0, 0.0, signal_power

    # Zero-padded FFT
    fft_output = np.fft.rfft(windowed, n=fft_size)
    power_spectrum = np.abs(fft_output) ** 2
    freq_bins = len(power_spectrum)

    freq_res = fs / float(fft_size)  # Hz per bin (~0.0293 Hz for 1024-pt)

    # Cardiac band bin boundaries
    bin_min = int(np.ceil(FREQ_MIN / freq_res))
    bin_max = min(int(np.floor(FREQ_MAX / freq_res)), freq_bins - 1)

    if bin_max <= bin_min:
        return 0.0, 0.0, signal_power

    cardiac_spectrum = power_spectrum[bin_min : bin_max + 1]
    peak_in_band = int(np.argmax(cardiac_spectrum))
    peak_bin = bin_min + peak_in_band
    max_power = float(power_spectrum[peak_bin])

    # SNR: peak power divided by mean non-peak power in cardiac band
    noise_mask = np.ones(len(cardiac_spectrum), dtype=bool)
    noise_mask[peak_in_band] = False
    noise_powers = cardiac_spectrum[noise_mask]
    noise_mean = float(np.mean(noise_powers)) if len(noise_powers) > 0 else 1.0
    snr = max_power / (noise_mean + 1e-6)

    # Sub-bin interpolation via parabolic vertex (native-lib.cpp L320–327)
    exact_peak_bin = float(peak_bin)
    if bin_min < peak_bin < bin_max:
        y1 = power_spectrum[peak_bin - 1]
        y2 = power_spectrum[peak_bin]
        y3 = power_spectrum[peak_bin + 1]
        den = y1 - 2.0 * y2 + y3
        if abs(den) > 1e-6:
            exact_peak_bin += 0.5 * (y1 - y3) / den

    bpm = exact_peak_bin * freq_res * 60.0
    return float(bpm), float(snr), signal_power


def compute_pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient between two 1D series."""
    if len(x) < 2 or len(y) < 2:
        return 0.0
    std_x = np.std(x)
    std_y = np.std(y)
    if std_x < 1e-7 or std_y < 1e-7:
        return 0.0
    corr = np.corrcoef(x, y)[0, 1]
    if np.isnan(corr) or np.isinf(corr):
        return 0.0
    return float(corr)


def analyze_pulse(
    all_frames: List[np.ndarray],
    face_boxes: List[Optional[Tuple[int, int, int, int]]],
    fps: float,
) -> PulseResult:
    """
    Extract rPPG pulse signals from forehead, left cheek, and right cheek.

    Parameters
    ----------
    all_frames : List[np.ndarray]
        List of all RGB video frames.
    face_boxes : List[Optional[Tuple[int, int, int, int]]]
        List of bounding boxes (x1, y1, x2, y2) matching all_frames or sampled.
        Can contain None for frames where face wasn't found.
    fps : float
        Video frame rate.

    Returns
    -------
    PulseResult
        BPM, SNR, cross-region correlations, screen flicker check, and plausibility.
    """
    result = PulseResult()

    if len(all_frames) < MIN_FRAMES_REQUIRED:
        result.error = f"Video too short for pulse analysis ({len(all_frames)} frames < {MIN_FRAMES_REQUIRED})"
        return result

    # Identify valid bounding boxes
    valid_boxes = [b for b in face_boxes if b is not None]
    if len(valid_boxes) < MIN_FRAMES_REQUIRED // 2:
        result.error = "Face detected in too few frames for pulse extraction"
        return result

    # Use the median face bounding box geometry if intermittent face tracking
    # (or per-frame box when available)
    median_x1 = int(np.median([b[0] for b in valid_boxes]))
    median_y1 = int(np.median([b[1] for b in valid_boxes]))
    median_x2 = int(np.median([b[2] for b in valid_boxes]))
    median_y2 = int(np.median([b[3] for b in valid_boxes]))
    default_box = (median_x1, median_y1, median_x2, median_y2)

    # Temporal RGB arrays for 3 regions:
    # 0: Forehead, 1: Left Cheek, 2: Right Cheek
    raw_rgb = {
        "forehead": [],
        "left_cheek": [],
        "right_cheek": [],
    }

    n_frames = len(all_frames)
    for i, frame in enumerate(all_frames):
        box = face_boxes[i] if (i < len(face_boxes) and face_boxes[i] is not None) else default_box
        bx1, by1, bx2, by2 = box
        bw = max(1, bx2 - bx1)
        bh = max(1, by2 - by1)
        h_frame, w_frame = frame.shape[:2]

        # 3 Regions (matching detector/faces.py get_face_regions)
        # Forehead: 45% width, 20% height, 10% top offset
        fh_w, fh_h = int(bw * 0.45), int(bh * 0.20)
        fh_x = max(0, min(w_frame - fh_w, bx1 + (bw - fh_w) // 2))
        fh_y = max(0, min(h_frame - fh_h, by1 + int(bh * 0.10)))

        # Left cheek: 20% width, 20% height, 50% top offset
        ch_w, ch_h = int(bw * 0.20), int(bh * 0.20)
        lc_x = max(0, min(w_frame - ch_w, bx1 + int(bw * 0.08)))
        lc_y = max(0, min(h_frame - ch_h, by1 + int(bh * 0.50)))

        # Right cheek
        rc_x = max(0, min(w_frame - ch_w, bx1 + int(bw * 0.72)))
        rc_y = lc_y

        # Compute mean RGB per region
        for key, (rx, ry, rw, rh) in [
            ("forehead", (fh_x, fh_y, fh_w, fh_h)),
            ("left_cheek", (lc_x, lc_y, ch_w, ch_h)),
            ("right_cheek", (rc_x, rc_y, ch_w, ch_h)),
        ]:
            patch = frame[ry : ry + rh, rx : rx + rw]
            if patch.size > 0:
                mean_c = np.mean(patch, axis=(0, 1))
            else:
                mean_c = np.array([0.0, 0.0, 0.0])
            raw_rgb[key].append(mean_c)

    # Convert to ndarray and resample to uniform 30 Hz
    region_pulses: Dict[str, np.ndarray] = {}
    for region_name, rgb_list in raw_rgb.items():
        rgb_arr = np.array(rgb_list, dtype=np.float64)  # shape (N, 3)
        resampled_rgb = resample_signals(rgb_arr, source_fps=fps, target_fs=TARGET_FS)
        r_c = resampled_rgb[:, 0]
        g_c = resampled_rgb[:, 1]
        b_c = resampled_rgb[:, 2]

        pos_sig = extract_pos_pulse(r_c, g_c, b_c)
        detrended = apply_fir_detrending(pos_sig, window_size=int(TARGET_FS))
        region_pulses[region_name] = detrended

    # Screen flicker check: green-red correlation on forehead signal (native-lib.cpp L202–229)
    fh_rgb = np.array(raw_rgb["forehead"], dtype=np.float64)
    if len(fh_rgb) >= 30:
        flicker_r = compute_pearson_corr(fh_rgb[:, 1], fh_rgb[:, 0])  # green vs red
        result.screen_flicker_corr = round(flicker_r, 4)
        result.is_screen_flicker = FLICKER_CHECK_ENABLED and flicker_r > FLICKER_CORR_THRESHOLD

    # Spectral analysis on forehead pulse (standard rPPG site)
    fh_pulse = region_pulses["forehead"]
    bpm, snr, pwr = compute_spectral_bpm_and_snr(fh_pulse, fs=TARGET_FS)
    result.bpm = round(bpm, 1)
    result.snr = round(snr, 2)
    result.signal_power = round(pwr, 5)

    # Cross-region correlations
    p_fh = region_pulses["forehead"]
    p_lc = region_pulses["left_cheek"]
    p_rc = region_pulses["right_cheek"]

    r_fh_lc = compute_pearson_corr(p_fh, p_lc)
    r_fh_rc = compute_pearson_corr(p_fh, p_rc)
    r_lc_rc = compute_pearson_corr(p_lc, p_rc)

    result.region_correlations = {
        "forehead_left_cheek": round(r_fh_lc, 3),
        "forehead_right_cheek": round(r_fh_rc, 3),
        "left_right_cheek": round(r_lc_rc, 3),
    }
    result.mean_region_corr = round(float(np.mean([r_fh_lc, r_fh_rc, r_lc_rc])), 3)

    # Plausibility check: human heart rate is typically 45–180 BPM, with good SNR and positive coherence
    result.bpm_plausible = (
        45.0 <= result.bpm <= 180.0
        and result.snr >= 2.0
        and result.signal_power >= 0.0005
        and not result.is_screen_flicker
    )
    result.valid = True
    return result


# ── CLI entry-point ─────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from detector.frames import extract_frames
    from detector.faces import detect_faces

    if len(sys.argv) < 2:
        print("Usage: python -m detector.pulse <video_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Reading video: {path} …")
    f_res = extract_frames(path)
    if f_res.error:
        print(f"Frame extraction error: {f_res.error}")
        sys.exit(1)

    print(f"Detecting faces on {len(f_res.classifier_frames)} frames …")
    fb = detect_faces(f_res.classifier_frames)

    # Build boxes aligned with all_frames
    all_boxes: List[Optional[Tuple[int, int, int, int]]] = []
    # Map classifier frame boxes onto nearest frames
    last_box: Optional[Tuple[int, int, int, int]] = None
    cf_idx_map = {idx: fb.faces[i] for i, idx in enumerate(f_res.classifier_indices)}

    for fi in range(len(f_res.all_frames)):
        if fi in cf_idx_map and cf_idx_map[fi].found:
            b = cf_idx_map[fi].box
            last_box = (b.x1, b.y1, b.x2, b.y2)
        all_boxes.append(last_box)

    print("Running pulse analysis …")
    pulse = analyze_pulse(f_res.all_frames, all_boxes, fps=f_res.fps)
    print(f"BPM:                 {pulse.bpm}")
    print(f"SNR:                 {pulse.snr}")
    print(f"BPM Plausible:       {pulse.bpm_plausible}")
    print(f"Mean Region Corr:    {pulse.mean_region_corr}")
    print(f"Region Corrs:        {pulse.region_correlations}")
    print(f"Screen Flicker Corr: {pulse.screen_flicker_corr} (flicker={pulse.is_screen_flicker})")
    print(f"Signal Power:        {pulse.signal_power}")
