"""
Shared fixtures for the SentinelSeal backend tests (suites 6-8).

The detector is replaced by a fake here so these tests check the backend's
rules (seals, holds, callbacks, deletion), not detection accuracy. Accuracy is
measured separately by eval/run_all.py on real videos.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def tmp_data(tmp_path, monkeypatch):
    from app.services import analysis, store as store_mod
    store_mod.store.set_path(tmp_path / "test.db")
    monkeypatch.setattr(analysis, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(analysis, "FRAMES_DIR", tmp_path / "frames")
    return tmp_path


@pytest.fixture()
def fake_detector():
    """Set what the detector returns for the next upload."""
    from app.services import analysis
    result = {"value": {
        "verdict": "SUSPICIOUS", "score": 0.87, "signed": False,
        "reasons": ["Face texture inconsistent in frames 41-88"],
        "flagged_frames": [], "model_version": "test", "bpm": None, "pulse_snr": None,
        "region_correlation": None, "face_found_rate": 0.9, "processing_seconds": 0.1,
    }}
    analysis.set_analyze_override(lambda path: dict(result["value"]))
    yield result
    analysis.set_analyze_override(None)


@pytest.fixture()
def client(tmp_data, fake_detector):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


class Phone:
    """An approver's phone: an EC P-256 key like StrongBox makes, and the payload it signs."""

    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        self.key = ec.generate_private_key(ec.SECP256R1())

    @property
    def public_key_b64(self) -> str:
        from cryptography.hazmat.primitives import serialization
        der = self.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return base64.b64encode(der).decode()

    def seal(self, payment: dict, approver_id: str = "md-rakesh", **overrides) -> dict:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        payload = {
            "session_id": payment["session_id"], "payment_id": payment["payment_id"],
            "approver_id": approver_id, "payee": payment["payee_name"],
            "amount_inr": payment["amount_inr"], "bpm": 72,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "device_id": "pixel-test", "snr": 5.0, "variance": 2.5,
        }
        payload.update(overrides)
        raw = json.dumps(payload).encode()
        sig = self.key.sign(raw, ec.ECDSA(hashes.SHA256()))
        return {"payload": base64.b64encode(raw).decode(),
                "signature": base64.b64encode(sig).decode(),
                "public_key": self.public_key_b64}


@pytest.fixture()
def phone():
    return Phone()


@pytest.fixture()
def enrolled_phone(client, phone):
    r = client.post("/api/v1/enrol", json={"approver_id": "md-rakesh", "public_key": phone.public_key_b64})
    assert r.status_code == 200, r.text
    return phone


def new_payment(client, amount=4_800_000, payee="Vendor Pvt Ltd", new_payee=True, approver="md-rakesh"):
    r = client.post("/api/v1/payments", json={
        "payee_name": payee, "payee_account": "50100234414417",
        "amount_inr": amount, "approver_id": approver, "new_payee": new_payee})
    assert r.status_code == 200, r.text
    return r.json()
