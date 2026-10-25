"""Approvers and phone enrolment."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import payments as pay
from app.services.crypto import InvalidPublicKeyError, load_public_key_from_der
from app.services.store import store

router = APIRouter()


class EnrolRequest(BaseModel):
    approver_id: str
    public_key: str = Field(..., description="Base64 DER (SubjectPublicKeyInfo) public key from StrongBox")
    attestation_chain: Optional[List[str]] = None


@router.get("/approvers", summary="Designated approvers for this company")
def list_approvers():
    return [pay.public_approver(a) for a in store.list_approvers()]


@router.post("/enrol", summary="Enrol an approver's phone (stores its public key)")
def enrol(req: EnrolRequest):
    a = store.get_approver(req.approver_id)
    if a is None:
        raise HTTPException(404, "Unknown approver")
    try:
        load_public_key_from_der(req.public_key)
    except InvalidPublicKeyError as e:
        raise HTTPException(400, f"Invalid public key: {e}")
    a.update(enrolled=True, public_key=req.public_key,
             attestation_chain=req.attestation_chain, enrolled_at=pay.now_iso())
    store.save_approver(a)
    return {"approver_id": a["approver_id"], "name": a["name"], "enrolled_at": a["enrolled_at"],
            # Attestation is stored but not yet checked server-side (planned).
            "attestation_checked": False}
