"""Payment lifecycle: create, instruction check, callback, release, reject, report."""

from __future__ import annotations

import secrets
import shutil
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services import analysis
from app.services import payments as pay
from app.services.session import session_manager
from app.services.store import store

router = APIRouter()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp"}


class CreatePayment(BaseModel):
    payee_name: str = Field(..., min_length=1)
    payee_account: str = Field(..., min_length=4)
    amount_inr: float = Field(..., gt=0)
    approver_id: str
    new_payee: bool = True


class CallbackBody(BaseModel):
    outcome: Literal["confirmed", "denied"]
    note: Optional[str] = None


class RejectBody(BaseModel):
    note: str = Field(..., min_length=1)


def _get(payment_id: str) -> dict:
    p = store.get_payment(payment_id)
    if p is None:
        raise HTTPException(404, "Payment not found")
    return p


@router.post("", summary="Create a payment (maker)")
def create(body: CreatePayment):
    approver = store.get_approver(body.approver_id)
    if approver is None:
        raise HTTPException(400, "Unknown approver")
    session = session_manager.create_session()
    p = pay.create_payment(payee_name=body.payee_name.strip(), payee_account=body.payee_account,
                           amount_inr=body.amount_inr, approver=approver,
                           new_payee=body.new_payee, session_id=session.session_id)
    session.metadata["payment_id"] = p["payment_id"]
    return p


@router.get("", summary="List payments (newest first)")
def list_payments(status: Optional[str] = None):
    items = store.list_payments()
    if status == "held":
        items = [p for p in items if p["status"] in pay.HELD]
        items.sort(key=lambda p: (p["status"] != pay.HELD_SUSPICIOUS, p.get("held_at") or ""))
    elif status:
        items = [p for p in items if p["status"] == status]
    return [pay.summary(p) for p in items]


@router.get("/{payment_id}", summary="Full payment record")
def get_payment(payment_id: str):
    return _get(payment_id)


@router.post("/{payment_id}/approval-session", summary="New QR session for the approver")
def new_session(payment_id: str):
    p = _get(payment_id)
    if p["status"] not in pay.OPEN:
        raise HTTPException(409, f"Payment is already {p['status']}")
    session = session_manager.create_session()
    session.metadata["payment_id"] = payment_id
    p["session_id"] = session.session_id
    pay.add_audit(p, "maker", "new approval QR")
    store.save_payment(p)
    return p


@router.post("/{payment_id}/instruction", summary="Upload the instruction video this payment is based on")
async def upload_instruction(payment_id: str, background: BackgroundTasks, file: UploadFile = File(...)):
    p = _get(payment_id)
    if p["status"] not in (pay.AWAITING_APPROVAL, pay.NOT_REQUIRED, pay.HELD_CALLBACK):
        raise HTTPException(409, f"Can't check an instruction for a payment that is {p['status']}")
    name = (file.filename or "upload").lower()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in VIDEO_EXTS:
        raise HTTPException(415, "Upload a video file (mp4, mov, avi, mkv, webm)")
    analysis.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = analysis.UPLOADS_DIR / f"{payment_id}-{secrets.token_hex(4)}{ext}"
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "Video is larger than 100 MB")
            out.write(chunk)
    p["status"] = pay.ANALYZING
    p["analysis_started_at"] = pay.now_iso()
    p["raw_clip_deleted_at"] = None
    p["thumbnails"] = []
    pay.add_audit(p, "maker", "instruction video uploaded", f"{size // 1024} KB")
    store.save_payment(p)
    background.add_task(analysis.analyze_instruction, payment_id, str(dest))
    return p


@router.get("/{payment_id}/frames/{n}", summary="Flagged frame thumbnail")
def frame(payment_id: str, n: int):
    path = analysis.thumbnail_path(payment_id, n)
    if not path.exists():
        raise HTTPException(404, "No thumbnail for this frame")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/{payment_id}/callback", summary="Record the callback outcome (fraud ops)")
def callback(payment_id: str, body: CallbackBody):
    p = _get(payment_id)
    if p["status"] not in pay.HELD:
        raise HTTPException(409, "Callback only applies to held payments")
    p["callback"] = {"outcome": body.outcome, "at": pay.now_iso(), "note": body.note}
    pay.add_audit(p, "fraud-ops", f"callback: approver {body.outcome}", body.note)
    store.save_payment(p)
    return p


@router.post("/{payment_id}/release", summary="Release the payment")
def release(payment_id: str):
    p = _get(payment_id)
    ok = (p["status"] in (pay.VERIFIED, pay.NOT_REQUIRED)
          or (p["status"] in pay.HELD and (p.get("callback") or {}).get("outcome") == "confirmed"))
    if not ok:
        reason = ("Held: the approver must confirm on the callback first"
                  if p["status"] in pay.HELD else f"Payment is {p['status']}")
        raise HTTPException(409, reason)
    was_held = p["status"] in pay.HELD
    pay.resolve(p, pay.RELEASED)
    pay.add_audit(p, "fraud-ops" if was_held else "checker", "released",
                  "cleared by callback" if was_held else None)
    store.save_payment(p)
    return p


@router.post("/{payment_id}/reject", summary="Reject the payment")
def reject(payment_id: str, body: RejectBody):
    p = _get(payment_id)
    if p["status"] in (pay.RELEASED, pay.REJECTED):
        raise HTTPException(409, f"Payment is already {p['status']}")
    pay.resolve(p, pay.REJECTED)
    pay.add_audit(p, "fraud-ops", "rejected", body.note)
    store.save_payment(p)
    return p


@router.post("/{payment_id}/report", summary="Create the fraud report for a rejected payment")
def report(payment_id: str):
    p = _get(payment_id)
    if p["status"] != pay.REJECTED:
        raise HTTPException(409, "Reports are created for rejected payments")
    if p.get("report") is None:
        p["report"] = {
            "report_id": f"SS-{p['payment_id'].upper()}-{secrets.token_hex(2).upper()}",
            "created_at": pay.now_iso(),
            "for_filing_at": "National Cyber Crime Reporting Portal (cybercrime.gov.in) / helpline 1930",
            "payment": {k: p.get(k) for k in ("payment_id", "payee_name", "payee_account_masked",
                                              "amount_inr", "approver_name", "created_at")},
            "verdict": p.get("verdict"),
            "evidence": {"clip_sha256": p.get("clip_sha256"), "flagged_frames": p.get("thumbnails"),
                         "raw_clip_deleted_at": p.get("raw_clip_deleted_at")},
            "callback": p.get("callback"),
            "audit": p.get("audit"),
        }
        pay.add_audit(p, "fraud-ops", "report created", p["report"]["report_id"])
        store.save_payment(p)
    return p["report"]
