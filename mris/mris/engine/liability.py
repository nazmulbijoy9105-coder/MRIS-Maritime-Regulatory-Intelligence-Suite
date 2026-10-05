"""Liability risk-flag advisor (Obj T, module 15 — ADVISORY ONLY).

Hard rule: this module is risk-flag advisory, never legal advice, and its
outputs can never downgrade a statutory GREEN (Principle 15). Flags:
    INFO    — informational
    WATCH   — action window opening (e.g. policy expiring)
    ELEVATED — exposure signal (expired cover, missing financial security)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

WARN_DAYS = 30


@dataclass
class InsurancePolicy:
    id: str
    entity_type: str                 # VESSEL | COMPANY
    entity_id: str
    policy_type: str                 # H&M | P&I | CLC | BUNKER | WRECK | LOH | K&R
    insurer: str
    policy_no: str
    issue_date: date
    expiry_date: date
    limit_amount: Optional[float] = None
    limit_currency: str = "USD"

    def status_at(self, at: date) -> str:
        if at > self.expiry_date:
            return "EXPIRED"
        if (self.expiry_date - at).days <= WARN_DAYS:
            return "EXPIRING"
        return "ACTIVE"


@dataclass
class LiabilityFlag:
    flag: str                        # INFO | WATCH | ELEVATED
    exposure_type: str
    vessel_id: Optional[str]
    rationale: str
    advisory: bool = True            # always True — never a statutory status


@dataclass
class LiabilityReport:
    vessel_id: str
    as_of: date
    policies: list[dict] = field(default_factory=list)
    flags: list[LiabilityFlag] = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        levels = {f.flag for f in self.flags}
        return "ELEVATED" if "ELEVATED" in levels else \
               "WATCH" if "WATCH" in levels else "INFO"

    def as_dict(self) -> dict:
        return {
            "vessel_id": self.vessel_id, "as_of": self.as_of.isoformat(),
            "risk_level": self.risk_level,
            "disclaimer": "risk-flag advisory layer — never legal advice; "
                          "never downgrades statutory compliance (Principle 15)",
            "policies": self.policies,
            "flags": [{"flag": f.flag, "exposure_type": f.exposure_type,
                       "vessel_id": f.vessel_id, "rationale": f.rationale,
                       "advisory": f.advisory} for f in self.flags],
        }


# financial-security covers expected on a trading vessel (MLC financial security
# + pollution conventions); missing cover is an ELEVATED advisory signal
EXPECTED_COVERS = ("P&I", "H&M")


def assess_liability(vessel_id: str, policies: list[InsurancePolicy], *,
                     as_of: date, exposures: Optional[list[dict]] = None) -> LiabilityReport:
    report = LiabilityReport(vessel_id=vessel_id, as_of=as_of)

    for p in policies:
        status = p.status_at(as_of)
        report.policies.append({
            "id": p.id, "policy_type": p.policy_type, "insurer": p.insurer,
            "policy_no": p.policy_no, "expiry_date": p.expiry_date.isoformat(),
            "limit_amount": p.limit_amount, "limit_currency": p.limit_currency,
            "status": status,
        })
        if status == "EXPIRED":
            report.flags.append(LiabilityFlag(
                flag="ELEVATED", exposure_type=p.policy_type,
                vessel_id=vessel_id,
                rationale=f"{p.policy_type} cover expired {p.expiry_date} "
                          f"(policy {p.policy_no}, {p.insurer}) — uninsured exposure"))
        elif status == "EXPIRING":
            report.flags.append(LiabilityFlag(
                flag="WATCH", exposure_type=p.policy_type,
                vessel_id=vessel_id,
                rationale=f"{p.policy_type} cover expires {p.expiry_date} "
                          f"(within {WARN_DAYS} days) — renewal window open"))

    covered = {p.policy_type for p in policies if p.status_at(as_of) != "EXPIRED"}
    already = {f.exposure_type for f in report.flags}
    for expected in EXPECTED_COVERS:
        if expected not in covered and expected not in already:
            report.flags.append(LiabilityFlag(
                flag="ELEVATED", exposure_type=expected, vessel_id=vessel_id,
                rationale=f"no valid {expected} cover on file — financial security "
                          f"exposure (check MLC Title 4 / pollution conventions)"))

    for exp in exposures or []:
        report.flags.append(LiabilityFlag(
            flag=exp.get("risk_flag", "INFO"), exposure_type=exp.get("exposure_type", "GENERAL"),
            vessel_id=vessel_id, rationale=exp.get("rationale", "recorded exposure")))

    if not report.flags:
        report.flags.append(LiabilityFlag(
            flag="INFO", exposure_type="GENERAL", vessel_id=vessel_id,
            rationale="covers complete and current; no exposure signals"))
    return report
