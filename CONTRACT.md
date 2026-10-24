# SentinelSeal Detection Contract  v1

> **Audience:** Part B (backend / web / Android).
> Read this file and the three sample JSONs below.
> Import `analyze` from `detector` — it accepts a file path and returns a dict matching this schema.

---

## Verdict fields

| Field | Type | Description |
|---|---|---|
| `verdict` | `str` | One of `VERIFIED`, `NEEDS_CALLBACK`, `SUSPICIOUS` |
| `score` | `float` | Fused deepfake score, 0.0 (clean) → 1.0 (fake). `null` when verdict is `VERIFIED`. |
| `signed` | `bool` | `true` only if an enrolled approver's key + payee/amount match. **Detection never sets this to `true`**; that is the backend's job. |
| `reasons` | `list[str]` | Plain-language reasons. Always at least one entry. |
| `flagged_frames` | `list[int]` | 0-indexed frame numbers where the classifiers scored highest. Empty list if not applicable. |
| `model_version` | `str` | Identifier for the fusion model version, e.g. `"fusion-v1"`. |
| `bpm` | `float \| null` | Estimated heart rate from the pulse module, or `null` if extraction failed. |
| `pulse_snr` | `float \| null` | Peak-to-mean SNR of the pulse signal, or `null`. |
| `region_correlation` | `float \| null` | Mean cross-region pulse correlation (forehead vs cheeks), or `null`. |
| `face_found_rate` | `float` | Fraction of sampled frames where a face was detected. 0.0–1.0. |
| `processing_seconds` | `float` | Wall-clock seconds the analysis took. |

---

## `analyze(path)` signature

```python
from detector import analyze

result: dict = analyze("/path/to/video.mp4")
```

- **Input:** absolute path to a video file (any format OpenCV can read).
- **Output:** a `dict` with the fields above.
- **Never raises.** Corrupt file, no face, audio-only, <2 s clip → returns `NEEDS_CALLBACK` with a reason.

---

## Sample verdicts

### VERIFIED (set by backend, not by detector)
```json
{
  "verdict": "VERIFIED",
  "score": null,
  "signed": true,
  "reasons": ["Signed by enrolled approver (approver-42)", "Payee and amount match"],
  "flagged_frames": [],
  "model_version": "fusion-v1",
  "bpm": null,
  "pulse_snr": null,
  "region_correlation": null,
  "face_found_rate": 1.0,
  "processing_seconds": 0.0
}
```

### NEEDS_CALLBACK
```json
{
  "verdict": "NEEDS_CALLBACK",
  "score": 0.38,
  "signed": false,
  "reasons": [
    "Not signed by any enrolled approver",
    "Fused score below high-confidence threshold"
  ],
  "flagged_frames": [14, 27],
  "model_version": "fusion-v1",
  "bpm": 72.4,
  "pulse_snr": 4.1,
  "region_correlation": 0.82,
  "face_found_rate": 0.95,
  "processing_seconds": 6.3
}
```

### SUSPICIOUS
```json
{
  "verdict": "SUSPICIOUS",
  "score": 0.87,
  "signed": false,
  "reasons": [
    "Face texture inconsistent in frames 41–88",
    "No consistent pulse between forehead and cheeks",
    "Not signed by any enrolled approver"
  ],
  "flagged_frames": [41, 52, 88],
  "model_version": "fusion-v1",
  "bpm": 0.0,
  "pulse_snr": 0.6,
  "region_correlation": 0.21,
  "face_found_rate": 0.73,
  "processing_seconds": 8.1
}
```

---

## `results/metrics.json` format

```json
{
  "run_id": "2026-10-24T14:05:10Z",
  "seed": 42,
  "hardware": "Intel i7-12700H, 32 GB RAM, no GPU",
  "suites": {
    "accuracy_deepspeak": {
      "balanced_accuracy": 0.0,
      "auc": 0.0,
      "fpr": 0.0,
      "fnr": 0.0,
      "n_real": 0,
      "n_fake": 0,
      "confusion_matrix": [[0,0],[0,0]],
      "bootstrap_ci_95": [0.0, 0.0]
    },
    "cross_dataset": { "...same schema..." },
    "ablation": {
      "classifier_only":  { "balanced_accuracy": 0.0, "auc": 0.0 },
      "classifier_pulse":  { "balanced_accuracy": 0.0, "auc": 0.0 },
      "full_fusion":       { "balanced_accuracy": 0.0, "auc": 0.0 }
    },
    "robustness": {
      "whatsapp_bitrate": { "balanced_accuracy": 0.0 },
      "360p":             { "balanced_accuracy": 0.0 },
      "dark_gamma":       { "balanced_accuracy": 0.0 },
      "blur":             { "balanced_accuracy": 0.0 },
      "15fps":            { "balanced_accuracy": 0.0 }
    },
    "latency": {
      "median_seconds": 0.0,
      "p95_seconds": 0.0
    }
  }
}
```
