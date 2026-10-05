"""Shipyard / shipbuilding readiness (Objs J & K, modules 11-12).

    project_readiness  — design approvals + construction surveys -> delivery ladder
    permit_risk        — hot-work / confined-space permit expiry exposure
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .status import Status


def _aware(dt: datetime) -> datetime:
    """Naive inputs are treated as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass
class DesignApproval:
    plan_type: str                   # HULL|STABILITY|MACHINERY|ELECTRICAL|FIRE|...
    status: str                      # SUBMITTED|APPROVED|CONDITIONAL|REJECTED


@dataclass
class ConstructionSurvey:
    survey_type: str                 # KEEL_LAYING|HULL|WELDING|MACHINERY|DOCKING|SEA_TRIAL|DELIVERY
    result: str                      # SATISFACTORY|DEFICIENCY|HOLD
    survey_date: Optional[str] = None


def project_readiness(approvals: list[DesignApproval],
                      surveys: list[ConstructionSurvey]) -> dict:
    """Delivery-readiness ladder (fail-closed):
       BLACK — a plan approval is REJECTED or a survey HOLD
       RED   — required plan approvals missing/REJECTED
       YELLOW— CONDITIONAL approvals or survey DEFICIENCY outstanding
       GREEN — all plans approved, all surveys satisfactory
    """
    if not approvals:
        return {"status": Status.BLACK, "reason": "no design approvals on file — cannot verify readiness"}

    if any(a.status == "REJECTED" for a in approvals) or \
       any(s.result == "HOLD" for s in surveys):
        return {"status": Status.BLACK,
                "reason": "rejected plan approval or survey hold — escalate to classification society / flag"}

    if any(a.status != "APPROVED" for a in approvals):
        return {"status": Status.RED,
                "reason": "plan approvals outstanding: "
                          + ", ".join(a.plan_type for a in approvals if a.status != "APPROVED")}

    if any(s.result == "DEFICIENCY" for s in surveys):
        return {"status": Status.YELLOW,
                "reason": "survey deficiencies outstanding: "
                          + ", ".join(s.survey_type for s in surveys if s.result == "DEFICIENCY")}

    return {"status": Status.GREEN,
            "reason": f"{len(approvals)} plan approval(s) approved, "
                      f"{len(surveys)} survey(s) satisfactory — delivery-ready"}


@dataclass
class WorkPermit:
    id: str
    permit_type: str                 # HOT_WORK|CONFINED_SPACE|ALOFT|ENCLOSED
    issued_at: datetime
    expiry_at: datetime
    status: str = "ACTIVE"           # ACTIVE|SUSPENDED|CLOSED|EXPIRED
    vessel_id: Optional[str] = None
    facility_id: Optional[str] = None


def permit_risk(permits: list[WorkPermit], now: Optional[datetime] = None) -> dict:
    """Permit-expiry exposure at a yard. Expired-but-open permits are the
    classic hot-work incident precursor — flagged ELEVATED."""
    now = _aware(now or datetime.now(timezone.utc))
    active, expired_open, suspended = [], [], []
    for p in permits:
        expiry = _aware(p.expiry_at)
        if p.status == "SUSPENDED":
            suspended.append(p)
        elif p.status == "ACTIVE" and now > expiry:
            expired_open.append(p)
        elif p.status == "ACTIVE":
            active.append(p)

    risk = "INFO"
    if expired_open:
        risk = "ELEVATED"
    elif suspended:
        risk = "WATCH"

    return {
        "risk": risk,
        "active": [p.id for p in active],
        "expired_but_open": [
            {"id": p.id, "permit_type": p.permit_type, "expiry_at": p.expiry_at.isoformat(),
             "vessel_id": p.vessel_id,
             "flag": "ELEVATED",
             "rationale": f"{p.permit_type} permit expired "
                          f"{p.expiry_at.isoformat()} but still ACTIVE — close or reissue"}
            for p in expired_open],
        "suspended": [p.id for p in suspended],
        "policy": "hot-work and confined-space permits are hard gates — work without a "
                  "valid permit is a stop-work condition (Obj K)",
    }
