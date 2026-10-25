"""
SentinelSeal payment lifecycle.

A payment wraps Part A's verdict (CONTRACT.md) with where the payment is now.
`verdict.verdict` is what the check said; `status` is where the payment is:
a SUSPICIOUS verdict can still end as RELEASED after a confirmed callback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.store import store

# ── Statuses ───────────────────────────────────────────────────────────
NOT_REQUIRED = "NOT_REQUIRED"            # rule did not trigger
AWAITING_APPROVAL = "AWAITING_APPROVAL"  # needs a seal or an instruction check
ANALYZING = "ANALYZING"                  # instruction video being checked
VERIFIED = "VERIFIED"                    # sealed by the designated approver
HELD_CALLBACK = "HELD_CALLBACK"          # unsealed, nothing strong found: callback
HELD_SUSPICIOUS = "HELD_SUSPICIOUS"      # strong signs of manipulation / bad seal
RELEASED = "RELEASED"
REJECTED = "REJECTED"

HELD = {HELD_CALLBACK, HELD_SUSPICIOUS}
OPEN = {AWAITING_APPROVAL, ANALYZING, HELD_CALLBACK, HELD_SUSPICIOUS}

# Check is required for new payees at or above this amount (placeholder, A9).
THRESHOLD_INR = 500_000

DEFAULT_APPROVERS = [
    {"approver_id": "md-rakesh", "name": "Rakesh M.", "role": "Managing Director",
     "registered_phone_masked": "+91 ••••• ••743"},
    {"approver_id": "cfo-anita", "name": "Anita S.", "role": "Chief Financial Officer",
     "registered_phone_masked": "+91 ••••• ••218"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def seed_approvers() -> None:
    """Create the demo approvers (not yet enrolled) if they don't exist."""
    for a in DEFAULT_APPROVERS:
        if store.get_approver(a["approver_id"]) is None:
            store.save_approver({**a, "enrolled": False, "public_key": None,
                                 "attestation_chain": None, "enrolled_at": None})


def public_approver(a: Dict[str, Any]) -> Dict[str, Any]:
    """Approver fields safe to send to the browser."""
    return {k: a.get(k) for k in
            ("approver_id", "name", "role", "registered_phone_masked", "enrolled", "enrolled_at")}


def mask_account(account: str) -> str:
    digits = "".join(ch for ch in account if ch.isalnum())
    return f"••{digits[-4:]}" if len(digits) >= 4 else "••••"


def add_audit(p: Dict[str, Any], actor: str, action: str, note: Optional[str] = None) -> None:
    p.setdefault("audit", []).append({"at": now_iso(), "actor": actor, "action": action, "note": note})


def create_payment(*, payee_name: str, payee_account: str, amount_inr: float,
                   approver: Dict[str, Any], new_payee: bool, session_id: str,
                   actor: str = "maker") -> Dict[str, Any]:
    check_required = bool(new_payee and amount_inr >= THRESHOLD_INR)
    p: Dict[str, Any] = {
        "payment_id": store.next_payment_id(),
        "payee_name": payee_name,
        "payee_account_masked": mask_account(payee_account),
        "amount_inr": amount_inr,
        "approver_id": approver["approver_id"],
        "approver_name": approver["name"],
        "registered_phone_masked": approver.get("registered_phone_masked"),
        "new_payee": new_payee,
        "check_required": check_required,
        "threshold_inr": THRESHOLD_INR,
        "session_id": session_id,
        "status": AWAITING_APPROVAL if check_required else NOT_REQUIRED,
        "verdict": None,
        "sealed_by": None,
        "sealed_at": None,
        "thumbnails": [],
        "clip_sha256": None,
        "raw_clip_deleted_at": None,
        "analysis_started_at": None,
        "held_at": None,
        "resolved_at": None,
        "resolution_seconds": None,
        "callback": None,
        "report": None,
        "created_at": now_iso(),
        "audit": [],
    }
    add_audit(p, actor, "created",
              "Check required: new payee at or above threshold" if check_required
              else "No extra check: existing payee or below threshold")
    store.save_payment(p)
    return p


def set_held(p: Dict[str, Any], verdict: Dict[str, Any], actor: str) -> None:
    """Apply a held verdict (NEEDS_CALLBACK or SUSPICIOUS) to an open payment."""
    p["verdict"] = verdict
    p["status"] = HELD_SUSPICIOUS if verdict["verdict"] == "SUSPICIOUS" else HELD_CALLBACK
    if not p.get("held_at"):
        p["held_at"] = now_iso()
    add_audit(p, actor, f"held: {verdict['verdict']}", "; ".join(verdict.get("reasons", [])[:2]))


def resolve(p: Dict[str, Any], status: str) -> None:
    p["status"] = status
    p["resolved_at"] = now_iso()
    if p.get("held_at"):
        p["resolution_seconds"] = round((_parse(p["resolved_at"]) - _parse(p["held_at"])).total_seconds(), 1)


def summary(p: Dict[str, Any]) -> Dict[str, Any]:
    v = p.get("verdict") or {}
    reasons: List[str] = v.get("reasons") or []
    return {k: p.get(k) for k in (
        "payment_id", "payee_name", "payee_account_masked", "amount_inr", "approver_name",
        "status", "created_at", "held_at", "resolved_at", "resolution_seconds",
        "analysis_started_at", "check_required")} | {
        "verdict": v.get("verdict"),
        "first_reason": reasons[0] if reasons else None,
    }


def format_inr(amount: float) -> str:
    """₹48,00,000 style (Indian digit grouping)."""
    n = int(round(amount))
    s = str(n)
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])
