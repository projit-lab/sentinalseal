### RAKSHAM finale · Team PenguinStack · Track 03

# SentinelSeal: finale playbook

Everything in one place: how we win, what to write on the disclosure form, what we build and how, the two-person plan, and the test workflow. Hours count from when the build window opens (H0). Ticks are saved only in your browser.

[1. How we win](#win)[2. Disclosure form](#form)[3. What we build](#build)[4. Two-person plan](#plan-sec)[5. Test workflow](#tests)[6. Stage 2 and Q&A](#stage)

1 · How we win

## The idea in one line

A deepfake can copy the CFO's face, but it can't copy a key locked inside the CFO's phone. SentinelSeal checks every high-value video payment instruction two ways. If it carries a valid signature from the enrolled approver's phone, it's VERIFIED. If it doesn't, our detector looks for manipulation, and the payment is held for a callback or fraud review instead of being released on trust.

## Where the points are

Tomorrow's top-10 cut is out of 100. Three things decide most of it:

1. **Test results and test completeness (30).** No organiser kit: we choose open datasets, run a full test workflow, and anyone can reproduce it with four commands. Completeness counts as much as accuracy.
2. **Working prototype (25).** A judge picks any video, it becomes a payment instruction, and the whole flow runs live.
3. **Own engineering (15) + alert and response (15) + delivery against Round 1 plan (15).** Our pulse features and fusion layer, a hold-callback-review flow that actually runs, and a clear commit history showing what's new since SentinelHard.

So the detector and its tests get most of the time. The signed-approval path stays because it's our differentiator and what Round 1 promised, but it's kept small.

## Three things to fix or know before coding

- **SentinelHard's server trusts any key.** `/verify` checks the signature against the public key sent in the same request. Fixed in B's H4–10 tasks.
- **None of these exist yet:** code read-back, video hash chain, Play Integrity, Redis, server-side attestation check. Say "planned" on stage for anything not built.
- **Reusing SentinelHard is allowed** if the commits clearly show what's new. Follow the commit rules below.

## Stage 1 rubric → what proves it

| Criterion | Pts | What the judge must see | Built in |
| --- | --- | --- | --- |
| Spot-check results and measured accuracy | 30 | Our test workflow: results on open datasets the models never trained on, error rates including FPR, robustness and ablation tables, named failure cases, and one command that reproduces it all | H0–20 (both) |
| Working prototype | 25 | Judge picks any video → it becomes a payment instruction → verdict → alert → action, all live | H0–4, H10–16 |
| Own engineering | 15 | Pulse-coherence features, trained fusion layer, decision service, hash chain. Every member can walk through the pipeline | H0–10 |
| Alert and response flow, as built | 15 | Hold, callback, analyst review and report all click-through. Clip deletion and on-device liveness actually running | H10–16 |
| Delivery against Round 1 plan | 15 | One slide: what the deck promised, what got built, what was cut and why | H20–24 |

2 · Disclosure form

## Before you fill it: push the baseline

The `sentinalseal` repo is empty. On one laptop:

```
git clone https://github.com/projit-lab/SentinelHard.git sentinalseal
cd sentinalseal
git remote set-url origin https://github.com/projit-lab/sentinalseal.git
git tag pre-finale
git push -u origin master --tags
git rev-parse HEAD       # master today = 49c04188dc420c4ed328792e4fe646000c2418bb
```

This keeps SentinelHard's August commit dates as proof it's pre-existing. If you'd rather start from the `accuracy-improved-version` branch, push that one and use the hash it prints.

## 1. Team & Repository

| Team Name | PenguinStack |
| --- | --- |
| Round 1 Submission ID | \[from Unstop\] |
| Repository URL | https://github.com/projit-lab/sentinalseal |
| Initial Commit Hash | 49c04188dc420c4ed328792e4fe646000c2418bb (if you pushed master) |
| Challenge Track | ☑ Track 3: Deepfake Detection for Financial Communications |
| Product statement | SentinelSeal is a verification layer for high-value payment approvals that checks whether a video instruction cryptographically came from the enrolled approver's own phone and shows a live human, and routes anything unproven to an out-of-band callback and human review before the bank releases the payment. |

## 2A. Pre-trained models, embeddings & third-party APIs

| Model / API | Provider | Checkpoint state | License |
| --- | --- | --- | --- |
| honi05/deepfake-detection (EfficientNet-B4) | Hugging Face | Off-the-shelf weights; fusion layer trained on-site | MIT |
| prithivMLmods/Deep-Fake-Detector-Model (SigLIP) | Hugging Face | Off-the-shelf | Apache-2.0 |
| MTCNN face detector (facenet-pytorch) | Open source | Off-the-shelf | MIT |
| Android Keystore / StrongBox, Key Attestation | Google (Android) | Platform API | Android SDK terms |
| Android SpeechRecognizer (only if read-back gets built) | Google (Android) | Platform API | Android SDK terms |

## 2B. Datasets

| Dataset / Source | Format | Provenance / Consent | Size |
| --- | --- | --- | --- |
| DeepSpeak v1 (UC Berkeley) | Video + audio | Public; consented participants; research / non-commercial use | \[n\] real + \[n\] fake subset |
| DFDC training sample (Kaggle) | Video | Public; competition terms | \~400 videos |
| Team recordings | Video | Team members; written consent | \[n\] clips |
| Team face-swap clips | Video | Consenting members' faces; labelled synthetic; not published | \[n\] clips |
| Synthetic payment records | Tabular | Generated by team; no real bank data | \[n\] rows |

If you use a face-swap tool (e.g. FaceFusion) to make the team clips, add it to 2A with its licence.

## 2C. Pre-built code & scaffolds

| Component / Module | Nature of code | Scope / Justification |
| --- | --- | --- |
| SentinelHard Android app (Kotlin) | StrongBox key, ECDSA signing, CameraX, QR scan | Our IOB CyberNova 2026 project, declared in Round 1. Approver-device layer. Tagged `pre-finale` |
| SentinelHard rPPG engine (C++ / OpenCV, POS) | On-device pulse extraction | Same project. On-device liveness only |
| SentinelHard backend + web (FastAPI, React) | Sessions, WebSocket, signature check, login UI | Scaffold. Reworked into payment verification during the finale |

## 3. Work to be built live

| Core detection / decision logic | Fused deepfake pipeline: MTCNN face crops → two pretrained classifiers + our pulse-coherence features across face regions (new Python port of our POS method) → fusion layer trained on-site → three-state verdict. A valid signature from an enrolled approver over payee and amount overrides detection. |
| --- | --- |
| Interfaces & alert workflows | Bank payment-release screen where the checker sees VERIFIED / NEEDS CALLBACK / SUSPICIOUS with reasons and flagged frames; fraud-ops console with hold queue, evidence pack, release / reject / report. Checks only run on high-value payments to new payees. |
| Safeguards & trust and safety | No auto-block: a flag means a reversible hold and a callback. Every alert says in plain words which signals fired. Raw clips deleted after the decision unless held; audit log; liveness on device. Measured false-positive rate shown in the app. |
| Target demo (MVP) | Jury picks any video; it arrives as a "CFO" RTGS instruction; system holds it with reasons → callback → analyst rejects and exports a report. Genuine approver signs on the enrolled phone → VERIFIED. A genuine user flagged by mistake clears via callback, with time shown. |

Section 4: each member ticks the boxes. Section 5: names and signatures (Prajit, Natasha, Shoaib; pick the lead).

3 · What we build, and how

## The flow

```
Maker creates RTGS payment (payee, amount) + attaches the instruction video
        │
        ├─ Signed by enrolled approver's phone? ──yes── payee/amount match? ──yes──▶ VERIFIED → checker releases
        │                                                 └─no──▶ SUSPICIOUS
        └─ Not signed ─▶ analyze(video)
                          ├─ score ≥ high threshold ─▶ SUSPICIOUS  → hold, fraud-ops queue, callback
                          └─ otherwise ─────────────▶ NEEDS CALLBACK → hold until approver confirms
                                                       (approver confirms → released, time logged)
```

An unsigned video is never VERIFIED, however clean it looks. The detector decides how worried to be, not whether to trust.

## A · Detection pipeline (`detector/`, new code)

| File | How |
| --- | --- |
| `frames.py` | OpenCV `VideoCapture`. Read up to 15 s. Keep every frame for the pulse, and every 6th–8th frame (about 4 fps) for the classifiers. |
| `faces.py` | facenet-pytorch MTCNN, largest face only, 224×224 crop with a small margin (match how the EfficientNet model was trained). Record face-found rate. |
| `classifiers.py` | EfficientNet-B4: `hf_hub_download("honi05/deepfake-detection", "best_model.pt")`, load with the author's model class, ImageNet normalisation, sigmoid per frame. SigLIP: Hugging Face image-classification pipeline on the same crops. Load both once at startup. |
| `pulse.py` | Port POS from `native-lib.cpp`: mean RGB of three regions (forehead, left cheek, right cheek, as fractions of the face box) every frame → POS with a \~1.6 s window → band-pass 0.7–4 Hz → FFT peak = BPM, peak power ratio = SNR. Then the correlation between the three regions' pulse signals. Real skin pulses together; swapped faces often don't. Needs about 8 s of video at full frame rate. |
| `features.py` | One vector per video: per model mean / max / top-10% frame score, temporal std, pulse SNR, region correlation, BPM plausibility, face-found rate. |
| `fusion.py` | scikit-learn `StandardScaler` + `LogisticRegression(class_weight="balanced")`, trained on the fit split only and saved with joblib. High threshold chosen so FPR on genuine fit videos is about 5%. |
| `reasons.py` | Turns features into sentences: "Face texture inconsistent in frames 41–88", "No consistent pulse between forehead and cheeks", "No face visible for 60% of the clip". |
| `analyze.py` | `analyze(path) → dict` following the shared contract. Any failure (no face, audio-only, corrupt, too short) returns NEEDS CALLBACK with a reason, never an exception. |

## B · Product (backend, web, phone)

| Part | How |
| --- | --- |
| Storage | SQLite (built-in `sqlite3`): payments, approvers (id → public key), verdicts, audit log. Replaces nothing that works; sessions can stay in memory. |
| `routers/payments.py` | POST /payments (payee, amount, approver_id, new_payee flag) · POST /payments/{id}/video (upload → background task runs analyze → store verdict → delete clip unless held) · GET /payments, GET /payments/{id} |
| `routers/enrol.py` | POST /enrol: approver_id + public key + attestation chain, stored in SQLite |
| Fix `routers/auth.py` /verify | Look up the key by approver_id and ignore the key in the request. Check signed payee and amount equal the payment record. Mark the session used. Result feeds the decision service. |
| `services/decision.py` | The flow above. Context rule: a check runs only if the payee is new and the amount is over a threshold (say ₹5 lakh). That's the alert-fatigue answer. |
| `routers/review.py` | POST /payments/{id}/callback (confirmed / denied) · /release · /reject · /report (JSON + simple PDF). Every action writes to the audit log with a timestamp. |
| Android | Add approverId, paymentId, payee, amount to `BiometricPayload`. After the QR scan, GET the payment and show "You are approving ₹48,00,000 to Vendor Pvt Ltd" before signing. Add an Enrol button that posts the public key. |
| React (existing Vite app) | Four screens: Maker (create payment, upload video), Checker (verdict card with reasons and flagged-frame thumbnails), Fraud-ops console (queue, evidence pack, actions, callback timer), Accuracy (reads `results/metrics.json`). |

### Shared contract: the verdict every part reads

```
{
  "payment_id": "p-1042", "payee": "Vendor Pvt Ltd", "amount": 4800000,
  "verdict": "SUSPICIOUS",          // VERIFIED | NEEDS_CALLBACK | SUSPICIOUS
  "score": 0.87,                    // fused, calibrated
  "signed": false,                  // true only if enrolled key + payee/amount match
  "reasons": [
    "Face texture inconsistent in frames 41–88",
    "No consistent pulse between forehead and cheeks",
    "Not signed by any enrolled approver"
  ],
  "flagged_frames": [41, 52, 88],
  "raw_clip_deleted_at": "2026-10-24T14:05:10Z",
  "model_version": "fusion-v3"
}
```

## Commit rules (organisers will read the history)

- Commit 1 = SentinelHard unchanged, message `baseline: SentinelHard (IOB CyberNova 2026, pre-existing)`. Tag it `pre-finale`.
- New work goes in new folders (`detector/`, `eval/`, `backend/app/services/decision.py`, `console/`), so `git diff pre-finale` shows the finale work at a glance.
- One commit per finished piece, pushed at least every hour. Prefixes: `feat(detector):`, `feat(eval):`, `feat(console):`, `fix:`. No squashing.
- Each person commits from their own GitHub account, so the history shows who built what.
- Keep a `FINALE.md` in the repo: one line per feature added, with the commit hash. It doubles as your "plan vs built" slide.

4 · Two-person plan

## Who does what

A · Detection B · Product BOTH

**A** owns everything that decides whether a video is fake, plus the numbers that prove it. **B** owns everything a bank user clicks and the signed-approval path. They meet at `analyze(path)`; B stubs it in the first hour so nobody waits. Whoever is stronger in Python/ML takes A.

### Never cut

- Any video in → verdict with plain-language reasons
- Held-out evaluation with FPR shown in the app
- Hold → callback → analyst review → report
- Clean data split: kit and held-out are never trained or tuned on
- A backup recording of the full demo

### Cut in this order if behind

- Already parked for two people: attestation check, spoken code read-back, video hash chain
- 1\. Second classifier in the ensemble (keep one)
- 2\. Report export (keep release / reject buttons)
- 3\. Console polish

Each cut goes on the "plan vs built" slide with a one-line reason.

5 · Test workflow

## Test workflow (part of the submission)

Judges score completeness as much as accuracy. Everything below lives in `eval/` and `tests/`, and one command rebuilds every number.

### Datasets

| Dataset | Why | Use |
| --- | --- | --- |
| **DeepSpeak v1** (UC Berkeley, Hany Farid lab) | People talking to a webcam, all consented. Face-swap and lip-sync fakes, some with cloned voices. Closest public match to a fake "CFO on a call". Free for research. | Main test set. Take a fixed subset by identity (e.g. 150 real + 150 fake), never train on it |
| **DFDC training sample** (Kaggle) | Different source and generators: shows cross-dataset behaviour | Fit the fusion layer on one part; the rest is a second test set |
| Team recordings + face-swaps | Indian conditions: phone cameras, WhatsApp compression, our own lighting | Supplementary FPR check; not public, so reported separately |
| *Not Celeb-DF* | The EfficientNet-B4 model was trained on it, so results there would be inflated | Excluded on purpose; say so |

### Test matrix

| Suite | What it shows | Owner |
| --- | --- | --- |
| 1. Accuracy per dataset and per fake type | Balanced accuracy, AUC, FPR, FNR, confusion matrix, 95% bootstrap intervals; face-swap vs lip-sync reported separately | A |
| 2. Cross-dataset | Fit on DFDC part, test on DeepSpeak (no tuning on the test set) | A |
| 3. Ablation | Classifier alone vs + pulse features vs full fusion. This is your own-engineering proof | A |
| 4. Robustness sweep | Same test set re-encoded with ffmpeg: WhatsApp-like bitrate, 360p, darker (gamma), blur, 15 fps. Metric drop per condition | A |
| 5. Genuine-user path | % of real videos sent to callback; time to clear through the UI | A + B |
| 6. Provenance (pytest) | Wrong key, unknown approver, edited payload, replayed session, payee/amount mismatch, expired session → expected verdict. Should be 100% | B |
| 7. Bad inputs (pytest) | No face, audio-only, corrupt file, 1 s clip, very large file → "callback required", never a crash | B |
| 8. End to end (pytest + API) | Upload → hold → callback → release / reject → report | B |
| 9. Latency | Seconds per video, median and 95th percentile, on the demo laptop's CPU | A |
| 10. Subgroups | Error rates by demographic group, if DeepSpeak's metadata includes it; otherwise list as not measured | A |

### Reproducibility (the README section judges will try)

```
git clone https://github.com/projit-lab/sentinalseal && cd sentinalseal
pip install -r eval/requirements.txt        # pinned versions
python eval/get_data.py                     # downloads the subsets listed in eval/splits/*.csv, checks file hashes
python eval/run_all.py --seed 42            # suites 1–4, 9, 10 → results/metrics.json + results/REPORT.md
pytest tests/                               # suites 6–8
```

- Commit the split files (video IDs + labels) and model checksums. Never commit the videos themselves.
- REPORT.md is generated, not hand-written. State hardware, run time and every known limitation.
- The SigLIP model's training data isn't fully documented, so overlap with test data can't be ruled out. Say so in the report.

## Round 1 plan vs what we're building

| Round 1 deck said | Now | Why |
| --- | --- | --- |
| Signature is primary, forensic model is fallback | Both core; detector gets most time | The kit tests unsigned media, which is also what real attacks look like |
| Pretrained forensic model with frame output | Pretrained classifier + our pulse features + trained fusion layer | A single score from one model wasn't enough; fused signals catch more and explain more |
| 1-second media hash chain | Fixed-size chunks of the recorded file (or cut) | Simpler; still catches cuts and inserts |
| Spoken code challenge | Stretch / planned | Lower rubric value than kit accuracy |
| Attestation rejects rooted devices | Stretch / planned | Phone sends the chain; server check not built yet |
| Validation on public sets + own clips, compression sweep | Full test workflow with 10 suites and one-command reproduction | Test completeness is scored as much as accuracy |
| Hold, callback, fraud-ops review, evidence pack | Built | Directly scored |

6 · Stage 2 and Q&A

## Stage 2: final presentation (if we make the top 10)

| Criterion | Pts | What to do |
| --- | --- | --- |
| Live user journey | 25 | Let the jury choose the video and the payee. Show attack arriving → hold → alert reasons → callback → analyst → report. No pre-recorded video unless the live one fails. |
| Problem and user | 20 | Open with the accounts executive at an Indian SME getting a video call from the "MD" before an RTGS cut-off. Maker-checker approves because the approval looked real. |
| Adversarial robustness | 20 | Show your own robustness table and failure list before they ask. Say what fools it and what you'd change. |
| Deployability and scale | 15 | Run by the bank's fraud-risk team inside corporate net-banking. Cost: measured CPU seconds per check × checks per day. Pilot: one bank, shadow mode (alerts only) for 3 months to measure false holds. |
| Responsible AI | 10 | Live: a genuine user gets flagged, the alert says why, the callback clears them, the timer shows how long it took. Show the "raw clip deleted at …" line. |
| Communication | 10 | Finish on time. "We don't know" is a scored answer, so use it when true. |

## Questions judges will ask

**"How would an attacker get past it?"**A new generator our classifier hasn't seen, adversarial noise on the frames, or very heavy compression. What helps: pulse features don't depend on the generator, and anything uncertain goes to callback instead of VERIFIED. What we'd add: more models in the ensemble and retraining on confirmed attacks.

**"What does it miss right now?"**Read straight from your failure-case list: no face visible, audio-only calls, side profiles, very dark rooms. Have the numbers ready.

**"What happens to a genuine user who gets flagged?"**Their payment is held, not rejected. The callback clears it in \[measured\] minutes, and the alert tells the checker why it fired.

**"Can't the attacker just use the signed app?"**Only from the enrolled phone, which needs to be in their hand. If they point it at a screen playing a deepfake, the screen-flicker check and the pulse check flag it.

**"What would it cost a bank?"**Measure seconds of CPU per clip today and turn it into cost per 1,000 checks. It only runs on high-value payments to new payees.