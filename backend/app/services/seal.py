"""
The seal check: did the designated approver's enrolled phone approve THIS payment?

Fixes the SentinelHard hole: the public key sent in the request is ignored.
The signature is checked only against the key enrolled for `approver_id`,
and the signed payee, amount, payment and session must match the record.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.auth import SealPayload, VerifyRequest
from app.services import payments as pay
from app.services.crypto import InvalidPublicKeyError, SignatureVerificationError, verify_signature
from app.services.liveness import SpoofingDetectedError, validate_liveness
from app.services.session import SessionStatus, session_manager
from app.services.store import store

logger = logging.getLogger(__name__)

# Last accepted request, kept in memory only for the replay demo (/demo/replay).
last_accepted: Dict[str, Any] = {}


def _seal_verdict(p: Dict[str, Any], approver: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "verdict": "VERIFIED", "score": None, "signed": True,
        "reasons": [f"Sealed by {approver['name']}'s enrolled phone",
                    "Payee and amount match the signed approval"],
        "flagged_frames": [], "model_version": "seal-v1", "bpm": None, "pulse_snr": None,
        "region_correlation": None, "face_found_rate": 0.0, "processing_seconds": 0.0,
    }


def _bad_seal_verdict(reason: str) -> Dict[str, Any]:
    return {
        "verdict": "SUSPICIOUS", "score": None, "signed": False,
        "reasons": [reason, "Not sealed by the designated approver"],
        "flagged_frames": [], "model_version": "seal-v1", "bpm": None, "pulse_snr": None,
        "region_correlation": None, "face_found_rate": 0.0, "processing_seconds": 0.0,
    }


def _flag(p: Optional[Dict[str, Any]], reason: str) -> None:
    """A bad seal against an open payment holds it as SUSPICIOUS. Resolved payments stay as they are."""
    if p is None or p["status"] not in pay.OPEN or p["status"] == pay.ANALYZING:
        if p is not None:
            pay.add_audit(p, "seal-check", "rejected seal attempt", reason)
            store.save_payment(p)
        return
    pay.set_held(p, _bad_seal_verdict(reason), actor="seal-check")
    store.save_payment(p)


def verify_seal(req: VerifyRequest, target_payment_id: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Returns (accepted, reason, payment).
    target_payment_id: the payment this seal is being applied to (defaults to the one inside
    the signed payload). The replay demo passes a different payment here.
    """
    # 1. Parse the signed payload.
    try:
        raw = base64.b64decode(req.payload)
        payload = SealPayload(**json.loads(raw))
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        return False, f"Invalid payload format: {e}", None

    target_id = target_payment_id or payload.payment_id
    p = store.get_payment(target_id)
    if p is None:
        return False, "Payment not found", None

    # 2. Enrolled key only. The key in the request is never trusted.
    approver = store.get_approver(payload.approver_id)
    if approver is None or not approver.get("enrolled") or not approver.get("public_key"):
        _flag(p, "Signed by a phone that is not enrolled for any approver")
        return False, "Approver is not enrolled", p
    try:
        verify_signature(req.payload, req.signature, approver["public_key"])
    except (SignatureVerificationError, InvalidPublicKeyError):
        _flag(p, "Signature does not match the approver's enrolled phone")
        return False, "Signature does not match the enrolled key", p

    # 3. The signature must be for THIS payment.
    if payload.payment_id != p["payment_id"]:
        original = store.get_payment(payload.payment_id)
        what = (f"{pay.format_inr(original['amount_inr'])} to {original['payee_name']}"
                if original else payload.payment_id)
        _flag(p, f"Signature was made for a different payment ({what})")
        return False, "Signature belongs to a different payment", p
    if payload.payee.strip() != p["payee_name"].strip() or abs(payload.amount_inr - p["amount_inr"]) > 0.5:
        _flag(p, "Signed payee or amount does not match this payment")
        return False, "Signed payee or amount does not match", p
    if payload.approver_id != p["approver_id"]:
        _flag(p, f"Signed by {approver['name']}, not the designated approver for this payment")
        return False, "Not the designated approver", p

    # 4. Single-use, fresh session.
    if p["status"] not in (pay.AWAITING_APPROVAL, pay.HELD_CALLBACK, pay.HELD_SUSPICIOUS, pay.ANALYZING):
        pay.add_audit(p, "seal-check", "rejected seal attempt", f"Payment already {p['status']}")
        store.save_payment(p)
        return False, f"Payment is already {p['status']}", p
    if payload.session_id != p["session_id"]:
        _flag(p, "Approval session does not belong to this payment")
        return False, "Session does not belong to this payment", p
    session = session_manager.get_session(payload.session_id)
    if session is None or session.is_expired:
        return False, "Approval session expired. Ask the maker for a new QR code", p
    if session.status != SessionStatus.PENDING:
        _flag(p, "This approval session was already used")
        return False, "Approval session already used", p
    age = (datetime.now(timezone.utc) - payload.timestamp).total_seconds()
    if abs(age) > settings.SESSION_EXPIRY_SECONDS:
        return False, "Signed approval is too old", p

    # 5. Live person on the approver's phone (SentinelHard liveness, unchanged).
    try:
        validate_liveness(bpm=payload.bpm, snr=payload.snr, variance=payload.variance)
    except SpoofingDetectedError as e:
        pay.add_audit(p, "seal-check", "liveness failed, approver can retry", str(e))
        store.save_payment(p)
        return False, str(e), p

    # 6. Sealed.
    session_manager.update_status(payload.session_id, SessionStatus.GRANTED,
                                  bpm=payload.bpm, device_id=payload.device_id)
    p["verdict"] = _seal_verdict(p, approver)
    p["status"] = pay.VERIFIED
    p["sealed_by"] = approver["name"]
    p["sealed_at"] = pay.now_iso()
    if p.get("held_at"):
        p["resolved_at"] = p["sealed_at"]
    pay.add_audit(p, approver["name"], "sealed", f"device {payload.device_id}")
    store.save_payment(p)
    last_accepted.clear()
    last_accepted.update(req.model_dump())
    return True, "Sealed", p
