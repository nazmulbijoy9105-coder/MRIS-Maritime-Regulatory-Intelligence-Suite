"""Compliance engine — result contract (Obj Z) + assembly + reproducibility.

Every result answers (Part 1.19):
    What requirement applies? Why? Source law? Exact provision? Legal version?
    Amended? In force on the relevant date? Supporting evidence? Rule executed?
    Facts used? Result? What's missing? Required action? Deadline? Consequence
    of non-correction? Lawyer review needed?

Principle 8:  result = f(law_version, rule_version, facts) — versions recorded.
Principle 10: as_of re-runs reproduce past results exactly.
Principle 15: advisory items can never flip a statutory GREEN lower.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

from .rules import RuleOutcome
from .status import Status, worst
from ..ilrmf import Tri

CONSEQUENCE = {
    Status.GREEN: "none",
    Status.YELLOW: "monitoring; scheduled action may be required",
    Status.RED: "operation may be unlawful; enforcement/penalty exposure",
    Status.BLACK: "undetermined — must be resolved by legal review before relying on this result",
}


@dataclass
class ResultContract:
    requirement: str
    why_applicable: str
    source_law: str
    provision: str
    legal_version: str
    amended: Optional[bool]
    in_force_on_date: Optional[bool]
    evidence: list[str]
    rule_executed: str
    facts_used: dict
    result: str
    missing: list[str]
    required_action: Optional[str]
    deadline: Optional[str]
    consequence: str
    lawyer_review_needed: bool


@dataclass
class ComplianceItem:
    obligation_id: str
    status: Status
    layer: str
    provision_id: str
    rule_version_id: str
    reason: str
    contract: ResultContract
    advisory: bool = False
    evidence_id: Optional[str] = None

    def as_dict(self) -> dict:
        c = self.contract
        return {
            "obligation_id": self.obligation_id,
            "status": self.status.value,
            "layer": self.layer,
            "provision": c.provision,
            "provision_id": self.provision_id,
            "rule_version_id": self.rule_version_id,
            "advisory": self.advisory,
            "reason": self.reason,
            "requirement": c.requirement,
            "why_applicable": c.why_applicable,
            "source_law": c.source_law,
            "legal_version": c.legal_version,
            "amended": c.amended,
            "in_force_on_date": c.in_force_on_date,
            "evidence": c.evidence,
            "rule_executed": c.rule_executed,
            "facts_used": c.facts_used,
            "result": c.result,
            "missing": c.missing,
            "required_action": c.required_action,
            "deadline": c.deadline,
            "consequence": c.consequence,
            "lawyer_review_needed": c.lawyer_review_needed,
        }


@dataclass
class ComplianceResult:
    company_id: str
    entity_type: str
    entity_id: str
    as_of_date: date
    items: list[ComplianceItem]
    law_versions_used: dict[str, str] = field(default_factory=dict)
    rule_versions_used: dict[str, str] = field(default_factory=dict)
    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc))

    @property
    def advisory_items(self) -> list[ComplianceItem]:
        return [i for i in self.items if i.advisory]

    @property
    def binding_items(self) -> list[ComplianceItem]:
        return [i for i in self.items if not i.advisory]

    @property
    def overall_status(self) -> Status:
        """Principle 15: advisory can never lower a statutory GREEN."""
        binding = self.binding_items
        if not binding:
            return Status.GREEN
        return worst(i.status for i in binding)

    @property
    def lawyer_review_queue(self) -> list[ComplianceItem]:
        return [i for i in self.items if i.contract.lawyer_review_needed]

    def as_dict(self) -> dict:
        return {
            "company_id": self.company_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "as_of_date": self.as_of_date.isoformat(),
            "overall_status": self.overall_status.value,
            "law_versions_used": self.law_versions_used,
            "rule_versions_used": self.rule_versions_used,
            "computed_at": self.computed_at.isoformat(),
            "items": [i.as_dict() for i in self.items],
            "lawyer_review_queue": [i.obligation_id for i in self.lawyer_review_queue],
        }


def item_from_outcome(outcome: RuleOutcome, *, layer: str,
                      requirement: str, why_applicable: str,
                      source_law: str, amended: Optional[bool],
                      in_force_on_date: Optional[bool],
                      advisory: bool = False,
                      deadline: Optional[str] = None) -> ComplianceItem:
    missing = [r for r in outcome.unknown_reasons] if outcome.unknown_reasons else []
    contract = ResultContract(
        requirement=requirement,
        why_applicable=why_applicable,
        source_law=source_law,
        provision=outcome.provision_id,
        legal_version=outcome.legal_version_id,
        amended=amended,
        in_force_on_date=in_force_on_date,
        evidence=outcome.evidence_required,
        rule_executed=f"{outcome.rule_id}@{outcome.rule_version_id}",
        facts_used=outcome.facts_used,
        result=outcome.status.value,
        missing=missing,
        required_action=(None if outcome.status is Status.GREEN
                         else f"resolve {outcome.status.value} item"),
        deadline=deadline,
        consequence=CONSEQUENCE[outcome.status],
        lawyer_review_needed=outcome.lawyer_review_needed,
    )
    return ComplianceItem(
        obligation_id=f"{outcome.rule_id}:{outcome.provision_id}",
        status=outcome.status,
        layer=layer,
        provision_id=outcome.provision_id,
        rule_version_id=outcome.rule_version_id,
        reason=outcome.reason,
        contract=contract,
        advisory=advisory,
    )


# ---------------------------------------------------------------------------
# Temporal selection (Principle 10 — historical reproducibility)
# ---------------------------------------------------------------------------

def select_version(versions: list[dict], as_of: date) -> Optional[dict]:
    """Pick the version whose [effective_from, effective_to) window covers
    as_of. Each version dict: {id, effective_from, effective_to}."""
    for v in versions:
        eff_from = v.get("effective_from")
        eff_to = v.get("effective_to")
        if eff_from is None:
            continue
        eff_from = eff_from if isinstance(eff_from, date) else date.fromisoformat(str(eff_from))
        eff_to = None if eff_to is None else (
            eff_to if isinstance(eff_to, date) else date.fromisoformat(str(eff_to)))
        if eff_from <= as_of and (eff_to is None or as_of < eff_to):
            return v
    return None


def provision_in_force(validity: list[dict], as_of: date) -> Optional[bool]:
    """provision_validity intervals -> in-force boolean at as_of.
    None when no interval covers the date (unknown => fail closed upstream)."""
    for v in validity:
        vf = v.get("valid_from")
        vt = v.get("valid_to")
        if vf is None:
            continue
        vf = vf if isinstance(vf, date) else date.fromisoformat(str(vf))
        vt = None if vt is None else (
            vt if isinstance(vt, date) else date.fromisoformat(str(vt)))
        if vf <= as_of and (vt is None or as_of < vt):
            return True
    return False
