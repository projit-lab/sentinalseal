"""
Unit tests for detector.pulse — rPPG extraction, POS algorithm, and coherence.
"""

from __future__ import annotations

import numpy as np
import pytest

from detector.pulse import (
    apply_fir_detrending,
    compute_pearson_corr,
    compute_spectral_bpm_and_snr,
    extract_pos_pulse,
    resample_signals,
    analyze_pulse,
    PulseResult,
)


def test_pos_algorithm_math():
    """Verify POS projection math behaves properly."""
    # Synthetic clean signals
    t = np.linspace(0, 5, 150)
    # Add a pulsatile component (cardiac wave is strongest in green channel)
    pulse_freq = 1.2  # 72 BPM
    cardiac = 0.05 * np.sin(2 * np.pi * pulse_freq * t)

    r = 150.0 + 0.01 * np.sin(2 * np.pi * pulse_freq * t)
    g = 120.0 + cardiac
    b = 100.0 + 0.01 * np.sin(2 * np.pi * pulse_freq * t)

    pos = extract_pos_pulse(r, g, b)
    assert len(pos) == 150
    assert np.all(np.isfinite(pos))

    # Empty input handling
    assert len(extract_pos_pulse(np.array([]), np.array([]), np.array([]))) == 0


def test_fir_detrending():
    """Verify moving average subtraction removes slow DC drift."""
    t = np.linspace(0, 5, 150)
    slow_drift = 2.0 * t
    sine = np.sin(2 * np.pi * 1.5 * t)
    signal = sine + slow_drift

    detrended = apply_fir_detrending(signal, window_size=30)
    assert len(detrended) == 150
    # Mean of detrended signal should be close to 0
    assert abs(np.mean(detrended)) < 0.2


def test_resample_signals():
    """Test uniform resampling from 20 fps to 30 fps."""
    # 2 seconds @ 20 fps = 40 samples
    sig_20fps = np.sin(np.linspace(0, 4 * np.pi, 40))
    resampled = resample_signals(sig_20fps, source_fps=20.0, target_fs=30.0)
    # 2 seconds @ 30 fps = 60 samples
    assert len(resampled) == 60


def test_spectral_bpm_and_snr_accuracy():
    """Verify FFT accurately detects a known frequency (e.g., 72 BPM = 1.2 Hz)."""
    fs = 30.0
    duration = 5.0  # 150 samples
    t = np.linspace(0, duration, int(duration * fs), endpoint=False)
    target_bpm = 72.0
    target_freq = target_bpm / 60.0  # 1.2 Hz

    clean_pulse = np.sin(2 * np.pi * target_freq * t)
    bpm, snr, pwr = compute_spectral_bpm_and_snr(clean_pulse, fs=fs)

    assert abs(bpm - target_bpm) < 2.5, f"Expected ~{target_bpm} BPM, got {bpm}"
    assert snr > 5.0, f"Expected high SNR for pure sine wave, got {snr}"
    assert pwr > 0.1


def test_pearson_corr():
    """Verify correlation calculation."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    assert pytest.approx(compute_pearson_corr(x, y), abs=1e-4) == 1.0

    # Inverted
    assert pytest.approx(compute_pearson_corr(x, -y), abs=1e-4) == -1.0

    # Constant signal (zero variance)
    assert compute_pearson_corr(np.zeros(5), y) == 0.0


def test_analyze_pulse_synthetic():
    """Run analyze_pulse on synthetic video frames."""
    fps = 30.0
    n_frames = 90  # 3 seconds
    frames = []
    boxes = []

    target_bpm = 80.0
    target_freq = target_bpm / 60.0

    for i in range(n_frames):
        t = i / fps
        cardiac_mod = int(10 * np.sin(2 * np.pi * target_freq * t))

        # Synthetic 100x100 frame with skin-tone block
        f = np.zeros((100, 100, 3), dtype=np.uint8)
        # Background
        f[:, :] = [30, 30, 30]
        # Face box area (20:80, 20:80)
        face_color = [180, 140 + cardiac_mod, 120]
        f[20:80, 20:80] = np.clip(face_color, 0, 255)

        frames.append(f)
        boxes.append((20, 20, 80, 80))

    res = analyze_pulse(frames, boxes, fps=fps)
    assert res.valid is True
    assert res.error is None
    assert abs(res.bpm - target_bpm) < 5.0
    assert res.mean_region_corr > 0.8  # All 3 regions have identical pulse in synthetic
    assert res.bpm_plausible is True
