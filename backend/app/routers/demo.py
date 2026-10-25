"""
DEMO ONLY: replay the last accepted signed approval against another payment.

Shows that a genuine seal can't be reused: the signature names its own
payment, payee and amount, so applying it elsewhere is flagged SUSPICIOUS.
Turn off with DEMO_TOOLS=false.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.auth import VerifyRequest
from app.services import seal
from app.services.store import store

router = APIRouter()


class ReplayBody(BaseModel):
    target_payment_id: str


@router.post("/replay", summary="DEMO ONLY: resend the last accepted seal against another payment")
def replay(body: ReplayBody):
    if not settings.DEMO_TOOLS:
        raise HTTPException(404, "Demo tools are off")
    if not seal.last_accepted:
        raise HTTPException(409, "No accepted seal yet. Approve a payment on the phone first.")
    if store.get_payment(body.target_payment_id) is None:
        raise HTTPException(404, "Payment not found")
    accepted, reason, p = seal.verify_seal(VerifyRequest(**seal.last_accepted), body.target_payment_id)
    return {"accepted": accepted, "reason": reason, "payment": p}
