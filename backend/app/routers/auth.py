"""
Seal verification router.

The approver's phone sends a payload signed by its StrongBox key. SentinelSeal
checks it ONLY against the key enrolled for that approver (the key in the
request is ignored), then checks the signed payee, amount, payment and session.
The old SentinelHard login flow, which trusted the key in the request, is gone.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas.auth import VerifyRequest, VerifyResponse
from app.services.seal import verify_seal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify a sealed payment approval from an enrolled approver's phone",
)
async def verify(request: VerifyRequest) -> VerifyResponse:
    accepted, reason, payment = verify_seal(request)
    logger.info("Seal %s: %s", "accepted" if accepted else "rejected", reason)
    return VerifyResponse(
        status="ACCESS_GRANTED" if accepted else "ACCESS_DENIED",
        session_id=(payment or {}).get("session_id") or "unknown",
        reason=None if accepted else reason,
        payment_id=(payment or {}).get("payment_id"),
        payment_status=(payment or {}).get("status"),
    )
