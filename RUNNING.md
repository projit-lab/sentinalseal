# Running SentinelSeal (finale demo)

All three parts run on the demo laptop; the phone must be on the same Wi-Fi.

## 1. Backend (port 8000)

```
cd backend
pip install -r requirements.txt -r ../detector/requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs. Data (SQLite, thumbnails) lives in `backend/data/`.
Delete that folder to start a demo from a clean slate.

## 2. Web screens (port 5173)

```
npm install
npm run dev -- --host
```

Open http://localhost:5173. If the backend is on another machine, create `.env` with
`VITE_API_BASE=http://<laptop-ip>:8000/api/v1`.

## 3. Approver phone

1. In `app/.../network/ApiClient.kt` set `BASE_URL` to `http://<laptop-ip>:8000/api/v1/` (`ipconfig` shows the IP).
2. Build and install from Android Studio.
3. Tap **Enrol this phone** once (registers the StrongBox key for `md-rakesh`).
4. On the web, create a payment and choose **Request sealed approval**; scan the QR, check the payee and amount, approve.

## Tests

```
cd backend && python -m pytest tests -q        # seal attacks, bad inputs, full journey
python -m pytest detector/tests -q              # detector units
```

## Accuracy page

Shows numbers only when `results/metrics.json` contains `"provenance": "measured"`,
which `eval/run_all.py` must write only after running `detector.analyze()` on real test videos.
