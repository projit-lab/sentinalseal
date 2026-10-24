# SentinelSeal — Feature Log

## Part A (Detection & Evaluation)

- `CONTRACT.md`: shared verdict schema, analyze() signature, sample JSONs, metrics.json format
- `detector/contract.py`: verdict constants and make_verdict() helper
- `detector/analyze.py`: stub analyze(path) → dict (NEEDS_CALLBACK until real pipeline wired)
- `detector/requirements.txt`: pinned CPU-only dependencies
