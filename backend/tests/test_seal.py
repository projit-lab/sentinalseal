"""Suite 6: provenance. Only the designated approver's enrolled phone can seal a payment."""

from __future__ import annotations

from tests.conftest import Phone, new_payment

V = "/api/v1/auth/verify"


def get(client, pid):
    return client.get(f"/api/v1/payments/{pid}").json()


def test_genuine_seal_verifies(client, enrolled_phone):
    p = new_payment(client)
    r = client.post(V, json=enrolled_phone.seal(p)).json()
    assert r["status"] == "ACCESS_GRANTED"
    p = get(client, p["payment_id"])
    assert p["status"] == "VERIFIED" and p["verdict"]["signed"] is True
    assert p["sealed_by"] == "Rakesh M."


def test_key_in_request_is_ignored(client, enrolled_phone):
    """The SentinelHard hole: an attacker signs with their own key and sends that key."""
    p = new_payment(client)
    attacker = Phone()
    r = client.post(V, json=attacker.seal(p)).json()
    assert r["status"] == "ACCESS_DENIED"
    p = get(client, p["payment_id"])
    assert p["status"] == "HELD_SUSPICIOUS"
    assert "enrolled phone" in p["verdict"]["reasons"][0]


def test_unenrolled_approver_rejected(client, phone):
    p = new_payment(client)
    r = client.post(V, json=phone.seal(p)).json()
    assert r["status"] == "ACCESS_DENIED"
    assert get(client, p["payment_id"])["status"] == "HELD_SUSPICIOUS"


def test_changed_amount_rejected(client, enrolled_phone):
    p = new_payment(client)
    r = client.post(V, json=enrolled_phone.seal(p, amount_inr=200_000)).json()
    assert r["status"] == "ACCESS_DENIED"
    assert "payee or amount" in get(client, p["payment_id"])["verdict"]["reasons"][0]


def test_changed_payee_rejected(client, enrolled_phone):
    p = new_payment(client)
    r = client.post(V, json=enrolled_phone.seal(p, payee="Someone Else Ltd")).json()
    assert r["status"] == "ACCESS_DENIED"


def test_wrong_approver_rejected(client, enrolled_phone):
    """Anita is enrolled too, but the payment names Rakesh as approver."""
    anita = Phone()
    client.post("/api/v1/enrol", json={"approver_id": "cfo-anita", "public_key": anita.public_key_b64})
    p = new_payment(client)
    r = client.post(V, json=anita.seal(p, approver_id="cfo-anita")).json()
    assert r["status"] == "ACCESS_DENIED"
    assert "not the designated approver" in get(client, p["payment_id"])["verdict"]["reasons"][0]


def test_replay_onto_another_payment_flagged(client, enrolled_phone):
    first = new_payment(client)
    assert client.post(V, json=enrolled_phone.seal(first)).json()["status"] == "ACCESS_GRANTED"
    second = new_payment(client, payee="Other Account Ltd")
    r = client.post("/api/v1/demo/replay", json={"target_payment_id": second["payment_id"]}).json()
    assert r["accepted"] is False
    p = get(client, second["payment_id"])
    assert p["status"] == "HELD_SUSPICIOUS"
    assert "different payment" in p["verdict"]["reasons"][0]
    assert get(client, first["payment_id"])["status"] == "VERIFIED"


def test_same_seal_twice_rejected(client, enrolled_phone):
    p = new_payment(client)
    req = enrolled_phone.seal(p)
    assert client.post(V, json=req).json()["status"] == "ACCESS_GRANTED"
    assert client.post(V, json=req).json()["status"] == "ACCESS_DENIED"
    assert get(client, p["payment_id"])["status"] == "VERIFIED"


def test_tampered_payload_rejected(client, enrolled_phone):
    import base64, json
    p = new_payment(client)
    req = enrolled_phone.seal(p)
    body = json.loads(base64.b64decode(req["payload"]))
    body["amount_inr"] = 1
    req["payload"] = base64.b64encode(json.dumps(body).encode()).decode()
    assert client.post(V, json=req).json()["status"] == "ACCESS_DENIED"


def test_stale_timestamp_rejected(client, enrolled_phone):
    p = new_payment(client)
    r = client.post(V, json=enrolled_phone.seal(p, timestamp="2026-01-01T00:00:00+00:00")).json()
    assert r["status"] == "ACCESS_DENIED"
    assert "too old" in r["reason"]


def test_failed_liveness_lets_approver_retry(client, enrolled_phone):
    p = new_payment(client)
    r = client.post(V, json=enrolled_phone.seal(p, bpm=0)).json()
    assert r["status"] == "ACCESS_DENIED"
    assert get(client, p["payment_id"])["status"] == "AWAITING_APPROVAL"
