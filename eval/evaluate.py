"""
SentinelSeal evaluation: runs the real detector on labelled videos and writes
measured results only.

    python eval/evaluate.py --labels eval/labels.csv [--robustness] [--seed 42]

labels.csv columns:  path,label,fake_type,source
    path       video file (absolute, or relative to the CSV)
    label      0 = genuine, 1 = fake
    fake_type  real | face_swap | lip_sync | other
    source     where it came from, e.g. deepspeak_v1, dfdc, team_consented

Outputs (read by the app's Accuracy page):
    results/metrics.json   "provenance": "measured", every number computed below
    results/misses.json    every wrong verdict, with the detector's first reason
    results/REPORT.md      human-readable summary
    results/per_file.csv   one row per video

Decision rule being measured: a video counts as "flagged fake" when the detector
returns SUSPICIOUS. Unsigned videos are always held in the product (NEEDS_CALLBACK
or SUSPICIOUS); this measures whether the detector raises the stronger alarm.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
RESULTS = REPO_ROOT / "results"

ROBUSTNESS = {
    "whatsapp_bitrate": ["-c:v", "libx264", "-b:v", "300k", "-vf", "scale=-2:640", "-an"],
    "360p": ["-vf", "scale=-2:360", "-an"],
    "dark_gamma": ["-vf", "eq=brightness=-0.2:gamma=0.6", "-an"],
    "blur": ["-vf", "boxblur=6", "-an"],
    "15fps": ["-r", "15", "-an"],
}


def read_labels(csv_path: Path) -> List[Dict[str, str]]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = Path(r["path"])
            if not p.is_absolute():
                p = (csv_path.parent / p).resolve()
            rows.append({"path": str(p), "label": int(r["label"]),
                         "fake_type": r.get("fake_type") or ("real" if r["label"] == "0" else "other"),
                         "source": r.get("source") or "unspecified"})
    missing = [r["path"] for r in rows if not Path(r["path"]).exists()]
    if missing:
        sys.exit(f"{len(missing)} labelled files not found, e.g. {missing[:3]}")
    if not rows:
        sys.exit("No rows in labels file")
    return rows


def metrics(y: List[int], flagged: List[int], scores: List[Optional[float]],
            rng: np.random.RandomState, n_boot: int = 1000) -> Dict:
    y_a, f_a = np.array(y), np.array(flagged)
    n_real, n_fake = int((y_a == 0).sum()), int((y_a == 1).sum())
    tp = int(((y_a == 1) & (f_a == 1)).sum()); fn = int(((y_a == 1) & (f_a == 0)).sum())
    fp = int(((y_a == 0) & (f_a == 1)).sum()); tn = int(((y_a == 0) & (f_a == 0)).sum())
    fpr = fp / n_real if n_real else None
    fnr = fn / n_fake if n_fake else None
    bal = (1 - fpr + 1 - fnr) / 2 if n_real and n_fake else None
    out = {"n_real": n_real, "n_fake": n_fake, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
           "fpr": fpr, "fnr": fnr, "balanced_accuracy": bal,
           "confusion_matrix": [[tn, fp], [fn, tp]], "auc": None, "bootstrap_ci_95": None}
    s = [(yy, sc) for yy, sc in zip(y, scores) if sc is not None]
    if s and len({yy for yy, _ in s}) == 2:
        from sklearn.metrics import roc_auc_score
        out["auc"] = float(roc_auc_score([a for a, _ in s], [b for _, b in s]))
    if bal is not None and len(y) >= 10:
        boots = []
        for _ in range(n_boot):
            idx = rng.randint(0, len(y), len(y))
            yb, fb = y_a[idx], f_a[idx]
            nr, nf = (yb == 0).sum(), (yb == 1).sum()
            if nr and nf:
                boots.append((((yb == 0) & (fb == 0)).sum() / nr + ((yb == 1) & (fb == 1)).sum() / nf) / 2)
        if boots:
            out["bootstrap_ci_95"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    return out


def run(rows, analyze, label=""):
    results = []
    for i, r in enumerate(rows, 1):
        t = time.perf_counter()
        v = analyze(r["path"])
        secs = time.perf_counter() - t
        results.append({**r, "verdict": v["verdict"], "score": v.get("score"),
                        "reason": (v.get("reasons") or [""])[0], "seconds": round(secs, 2),
                        "face_found_rate": v.get("face_found_rate")})
        print(f"  {label}[{i}/{len(rows)}] {Path(r['path']).name}: {v['verdict']} ({secs:.1f}s)", flush=True)
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--robustness", action="store_true", help="also re-encode each video with ffmpeg and re-test")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = np.random.RandomState(args.seed)

    from detector import analyze
    from detector.classifiers import get_effnet_detector, get_siglip_detector
    used = [n for n, d in (("EfficientNet-B4 (honi05)", get_effnet_detector()),
                           ("SigLIP (prithivMLmods)", get_siglip_detector())) if d.load()]
    if not used:
        sys.exit("No deepfake model loaded (run: python -m detector.check_models). Refusing to write results.")

    rows = read_labels(args.labels)
    print(f"Evaluating {len(rows)} videos with: {', '.join(used)}")
    res = run(rows, analyze)

    y = [r["label"] for r in res]
    flag = [1 if r["verdict"] == "SUSPICIOUS" else 0 for r in res]
    main_suite = metrics(y, flag, [r["score"] for r in res], rng)
    by_type = {}
    for ft in sorted({r["fake_type"] for r in res if r["label"] == 1}):
        sub = [r for r in res if r["label"] == 0 or r["fake_type"] == ft]
        by_type[ft] = metrics([r["label"] for r in sub],
                              [1 if r["verdict"] == "SUSPICIOUS" else 0 for r in sub],
                              [r["score"] for r in sub], rng, n_boot=0)
    main_suite["by_fake_type"] = by_type
    by_source = {}
    for src in sorted({r["source"] for r in res}):
        sub = [r for r in res if r["source"] == src]
        by_source[src] = metrics([r["label"] for r in sub],
                                 [1 if r["verdict"] == "SUSPICIOUS" else 0 for r in sub],
                                 [r["score"] for r in sub], rng, n_boot=0)

    secs = [r["seconds"] for r in res]
    suites = {
        "accuracy_deepspeak": main_suite,  # key kept for the app; see "test_set" for what it contains
        "by_source": by_source,
        "latency": {"median_seconds": statistics.median(secs),
                    "p95_seconds": float(np.percentile(secs, 95)), "n": len(secs)},
    }

    if args.robustness:
        if not shutil.which("ffmpeg"):
            print("ffmpeg not found: skipping robustness")
        else:
            rob = {}
            with tempfile.TemporaryDirectory() as tmp:
                for cond, ff in ROBUSTNESS.items():
                    variants = []
                    for r in rows:
                        out = Path(tmp) / f"{cond}_{Path(r['path']).stem}.mp4"
                        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", r["path"], *ff, str(out)], check=False)
                        if out.exists():
                            variants.append({**r, "path": str(out)})
                    vr = run(variants, analyze, label=f"{cond} ")
                    m = metrics([v["label"] for v in vr], [1 if v["verdict"] == "SUSPICIOUS" else 0 for v in vr],
                                [v["score"] for v in vr], rng, n_boot=0)
                    rob[cond] = {"balanced_accuracy": m["balanced_accuracy"], "fpr": m["fpr"],
                                 "fnr": m["fnr"], "auc": m["auc"], "n": len(vr)}
            suites["robustness"] = rob

    counts = {}
    for r in res:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    test_set = ", ".join(f"{k} ({v})" for k, v in counts.items())
    try:
        import torch
        hw = f"{platform.platform()}, {platform.processor() or platform.machine()}, torch {torch.__version__} (CPU)"
    except Exception:
        hw = platform.platform()

    RESULTS.mkdir(exist_ok=True)
    metrics_doc = {
        "provenance": "measured",
        "run_id": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": args.seed, "hardware": hw, "models_used": used,
        "test_set": test_set, "labels_file": str(args.labels),
        "decision_rule": "flagged fake = SUSPICIOUS verdict; genuine videos flagged = false positives",
        "suites": suites,
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics_doc, indent=2), encoding="utf-8")
    misses = [{"file": Path(r["path"]).name, "true_label": "fake" if r["label"] else "genuine",
               "verdict": r["verdict"], "score": r["score"], "reason": r["reason"]}
              for r, f in zip(res, flag) if f != r["label"]]
    (RESULTS / "misses.json").write_text(json.dumps(misses, indent=2), encoding="utf-8")
    with open(RESULTS / "per_file.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        w.writeheader(); w.writerows(res)

    pct = lambda x: "not measured" if x is None else f"{x * 100:.1f}%"
    ci = main_suite["bootstrap_ci_95"]
    lines = [
        "# SentinelSeal: measured evaluation", "",
        f"Run {metrics_doc['run_id']} · seed {args.seed} · {hw}", "",
        f"Models: {', '.join(used)}  ", f"Test set: {test_set}  ",
        f"Rule: {metrics_doc['decision_rule']}", "",
        "| Metric | Value |", "|---|---|",
        f"| Genuine videos wrongly flagged (FPR) | {pct(main_suite['fpr'])} of {main_suite['n_real']} |",
        f"| Fakes missed (FNR) | {pct(main_suite['fnr'])} of {main_suite['n_fake']} |",
        f"| Balanced accuracy | {pct(main_suite['balanced_accuracy'])}"
        + (f" (95% CI {pct(ci[0])}–{pct(ci[1])})" if ci else "") + " |",
        f"| AUC | {'not measured' if main_suite['auc'] is None else round(main_suite['auc'], 3)} |",
        f"| Median time per video | {suites['latency']['median_seconds']:.1f} s |", "",
        "## By fake type", "", "| Type | Balanced accuracy | Missed |", "|---|---|---|",
        *[f"| {k} | {pct(v['balanced_accuracy'])} | {pct(v['fnr'])} |" for k, v in by_type.items()], "",
    ]
    if "robustness" in suites:
        lines += ["## Robustness", "", "| Condition | Balanced accuracy | FPR |", "|---|---|---|",
                  *[f"| {k} | {pct(v['balanced_accuracy'])} | {pct(v['fpr'])} |" for k, v in suites["robustness"].items()], ""]
    lines += ["## Failure cases", "", *(f"- `{m['file']}`: {m['true_label']}, got {m['verdict']}: {m['reason']}"
                                         for m in misses), "" if misses else "- none in this run", "",
              "Small test sets give wide confidence intervals; read the CI, not just the point value."]
    (RESULTS / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote results/metrics.json, misses.json, per_file.csv, REPORT.md  "
          f"(FPR {pct(main_suite['fpr'])}, FNR {pct(main_suite['fnr'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
