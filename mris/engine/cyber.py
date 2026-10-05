"""Cyber risk-management baseline (Obj R) — IMO MSC.428(98) + MSC-FAL.1/Circ.3.

Five-step functional model (identify / protect / detect / respond / recover),
assessed per control with the standard status ladder. Rollup is worst-of;
missing assessment data is UNKNOWN -> BLACK (fail-closed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .status import Status, worst

MSC428_CONTROLS = [
    ("MSC.428", "ID-1", "Identify cyber risk management systems",
     "Inventory OT/ICS, navigation (ECDIS/AIS), business and crew/passenger systems."),
    ("MSC-FAL.1/Circ.3", "PR-2", "Protect — access control & segmentation",
     "Role-based access, network segmentation of safety-critical systems."),
    ("MSC-FAL.1/Circ.3", "PR-3", "Protect — patches, backups & encryption",
     "Managed patching, encrypted backups, offline restore capability."),
    ("MSC-FAL.1/Circ.3", "DE-4", "Detect — monitoring & anomaly detection",
     "Logging, intrusion/anomaly detection on IT and OT networks."),
    ("MSC-FAL.1/Circ.3", "RS-5", "Respond — cyber incident response plan",
     "Documented response plan, roles, escalation, drills."),
    ("MSC-FAL.1/Circ.3", "RC-6", "Recover — restoration & lessons learned",
     "Restore operations from backup; post-incident review."),
    ("IMO Res.A.1068", "GV-7", "Governance — company accountability",
     "Named responsible officer, budget, third-party risk management."),
    ("national", "NAT-8", "National cyber-statute mapping",
     "Map controls to applicable national ICT/cyber statutes (BD: ICT Act 2006 / Cyber Security Act 2023 — VERIFY mapping)."),
]

_STATUS_NOTE = {
    Status.GREEN: "implemented and evidenced",
    Status.YELLOW: "partially implemented / evidence pending",
    Status.RED: "not implemented — gap against control",
    Status.BLACK: "assessment missing or uncertain — fail-closed",
}


@dataclass
class CyberAssessment:
    control_ref: str
    title: str
    status: Status
    note: str = ""
    assessed_by: Optional[str] = None
    evidence_id: Optional[str] = None


@dataclass
class CyberPosture:
    entity_type: str
    entity_id: str
    assessments: list[CyberAssessment] = field(default_factory=list)

    @property
    def overall(self) -> Status:
        return worst(a.status for a in self.assessments) if self.assessments else Status.BLACK

    def as_dict(self) -> dict:
        return {
            "entity_type": self.entity_type, "entity_id": self.entity_id,
            "overall": self.overall.value,
            "framework": "IMO MSC.428(98) + MSC-FAL.1/Circ.3 five-step model",
            "assessments": [
                {"control_ref": a.control_ref, "title": a.title,
                 "status": a.status.value, "note": a.note or _STATUS_NOTE[a.status],
                 "assessed_by": a.assessed_by, "evidence_id": a.evidence_id}
                for a in self.assessments],
        }


def assess_cyber(entity_type: str, entity_id: str,
                 control_status: dict[str, str]) -> CyberPosture:
    """control_status: control_ref -> GREEN|YELLOW|RED|BLACK.

    Controls absent from the input are BLACK (assessment missing => fail-closed).
    """
    posture = CyberPosture(entity_type=entity_type, entity_id=entity_id)
    for framework, ref, title, _desc in MSC428_CONTROLS:
        raw = control_status.get(ref)
        try:
            status = Status(raw) if raw else Status.BLACK
        except ValueError:
            status = Status.BLACK
        posture.assessments.append(CyberAssessment(
            control_ref=ref, title=title, status=status))
    return posture
