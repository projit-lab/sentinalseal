# SentinelSeal — Feature Log

## Part A (Detection & Evaluation)

- `CONTRACT.md`: shared verdict schema, analyze() signature, sample JSONs, metrics.json format
- `detector/contract.py`: verdict constants (VERIFIED, NEEDS_CALLBACK, SUSPICIOUS) and make_verdict() helper
- `detector/requirements.txt`: pinned CPU-only dependencies with cross-platform compatibility
- `detector/frames.py`: video frame extraction (up to 15s cap, all frames for pulse, every 7th frame for classifiers)
- `detector/faces.py`: MTCNN face detection, 224x224 crop with margin, 3-region ROI extraction (forehead, left cheek, right cheek)
- `detector/pulse.py`: Python port of POS rPPG from `native-lib.cpp`, 1024-pt FFT, SNR, BPM, 3-region coherence correlation, and screen flicker detection
- `detector/classifiers.py`: pretrained ensemble (EfficientNet-B4 `honi05` + SigLIP `prithivMLmods`) with flagged frame tracking
- `detector/features.py`: unified 16-element feature vector aggregation across face, classifiers, and pulse
- `detector/fusion.py`: calibrated StandardScaler + LogisticRegression fusion decision layer (calibrated high threshold for ~5% FPR)
- `detector/reasons.py`: plain-language forensic explanation generation for checkers and fraud ops
- `detector/analyze.py`: complete end-to-end `analyze(path) -> dict` pipeline adhering to contract, never-raise guarantee
- `detector/tests/`: unit tests across frames, faces, pulse, features, fusion, reasons, and analyze contract (26 passing tests)
- `eval/requirements.txt`: pinned evaluation dependencies
- `eval/splits/`: committed split manifests (`dfdc_fit.csv`, `deepspeak_test.csv`, `team_supplementary.csv`)
- `eval/get_data.py`: dataset verifier and fixture generator
- `eval/run_all.py`: benchmark suite runner (Suites 1–4, 9, 10) reproducing all metrics with `--seed 42`
- `results/metrics.json`: contract-compliant benchmark results for React Accuracy view
- `results/REPORT.md`: comprehensive evaluation report with ablation, robustness, latency, and limitation disclosures
