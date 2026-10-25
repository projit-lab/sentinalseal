"""Suites 7 and 8: bad inputs and the end-to-end journey (upload, hold, callback, release/reject, report)."""

from __future__ import annotations

from tests.conftest import new_payment

P = "/api/v1/payments"


def upload(client, pid, name="instruction.mp4", data=b"\x00" * 2048):
    return client.post(f"{P}/{pid}/instruction", files={"file": (name, data, "video/mp4")})


def test_rule_not_triggered_for_small_or_known_payee(client):
    assert new_payment(client, amount=100_000)["status"] == "NOT_REQUIRED"
    assert new_payment(client, new_payee=False)["status"] == "NOT_REQUIRED"
    assert new_payment(client)["status"] == "AWAITING_APPROVAL"


def test_suspicious_upload_held_and_clip_deleted(client, tmp_data):
    p = new_payment(client)
    assert upload(client, p["payment_id"]).status_code == 200
    p = client.get(f"{P}/{p['payment_id']}").json()
    assert p["status"] == "HELD_SUSPICIOUS"
    assert p["verdict"]["signed"] is False
    assert any("enrolled approver" in r for r in p["verdict"]["reasons"])
    assert p["raw_clip_deleted_at"] is not None and p["clip_sha256"]
    assert not any((tmp_data / "uploads").iterdir())


def test_unsigned_clean_video_is_never_verified(client, fake_detector):
    fake_detector["value"] = {**fake_detector["value"], "verdict": "VERIFIED", "score": 0.05}
    p = new_payment(client)
    upload(client, p["payment_id"])
    p = client.get(f"{P}/{p['payment_id']}").json()
    assert p["status"] == "HELD_CALLBACK" and p["verdict"]["verdict"] == "NEEDS_CALLBACK"


def test_detector_crash_holds_for_callback(client):
    from app.services import analysis

    def boom(path):
        raise RuntimeError("corrupt file")
    analysis.set_analyze_override(boom)
    p = new_payment(client)
    upload(client, p["payment_id"])
    p = client.get(f"{P}/{p['payment_id']}").json()
    assert p["status"] == "HELD_CALLBACK"
    assert p["raw_clip_deleted_at"] is not None


def test_non_video_upload_refused(client):
    p = new_payment(client)
    assert upload(client, p["payment_id"], name="notes.txt").status_code == 415


def test_held_payment_needs_confirmed_callback_to_release(client):
    p = new_payment(client)
    upload(client, p["payment_id"])
    pid = p["payment_id"]
    assert client.post(f"{P}/{pid}/release").status_code == 409
    client.post(f"{P}/{pid}/callback", json={"outcome": "confirmed"})
    r = client.post(f"{P}/{pid}/release").json()
    assert r["status"] == "RELEASED" and r["resolution_seconds"] is not None


def test_denied_callback_reject_and_report(client):
    p = new_payment(client)
    upload(client, p["payment_id"])
    pid = p["payment_id"]
    client.post(f"{P}/{pid}/callback", json={"outcome": "denied"})
    assert client.post(f"{P}/{pid}/report").status_code == 409
    assert client.post(f"{P}/{pid}/reject", json={"note": "Approver denied on callback"}).json()["status"] == "REJECTED"
    rep = client.post(f"{P}/{pid}/report").json()
    assert rep["report_id"].startswith("SS-") and rep["callback"]["outcome"] == "denied"
    actions = [a["action"] for a in client.get(f"{P}/{pid}").json()["audit"]]
    assert "rejected" in actions and "report created" in actions


def test_held_queue_puts_suspicious_first(client, fake_detector):
    fake_detector["value"] = {**fake_detector["value"], "verdict": "NEEDS_CALLBACK"}
    a = new_payment(client)
    upload(client, a["payment_id"])
    fake_detector["value"] = {**fake_detector["value"], "verdict": "SUSPICIOUS"}
    b = new_payment(client)
    upload(client, b["payment_id"])
    held = client.get(f"{P}?status=held").json()
    assert [h["payment_id"] for h in held] == [b["payment_id"], a["payment_id"]]


def test_metrics_never_shows_unmeasured_numbers(client, tmp_path, monkeypatch):
    from app.routers import metrics
    monkeypatch.setattr(metrics, "RESULTS_DIR", tmp_path)
    assert client.get("/api/v1/metrics").json()["measured"] is False
    (tmp_path / "metrics.json").write_text('{"suites": {"accuracy_deepspeak": {"fpr": 0.0}}}')
    assert client.get("/api/v1/metrics").json()["measured"] is False
    (tmp_path / "metrics.json").write_text('{"provenance": "measured", "suites": {}}')
    assert client.get("/api/v1/metrics").json()["measured"] is True
