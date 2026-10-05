"""Incident & casualty module (Obj S, Part 8.6).

Reportable incident -> regulatory notification deadlines -> corrective
actions -> closure. Deadlines are computed deterministically from the
incident type and occurrence time; overdue notifications escalate.

The deadline table below is demo-grade regulatory metadata (marked
EXTRACTED_BY_AI in the corpus policy sense) — production values must be
verified against the exact provisions in the legal corpus before use.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

# (authority, provision basis, hours after occurrence, scope)
NOTIFICATION_RULES: dict[str, list[tuple[str, str, int, str]]] = {
    "POLLUTION": [
        ("BD-DOS", "MARPOL Annex I Reg 11 / MSO pollution reporting", 1,
         "initial report without delay"),
        ("BD-DOE", "Environment Conservation Act 1995 (spill notification)", 24,
         "formal notification to environment authority"),
        ("FLAG-STATE", "MARPOL Annex I Reg 11(3)", 720,
         "written report within 30 days"),
    ],
    "COLLISION": [
        ("BD-DOS", "MSO casualty inquiry provisions", 24,
         "casualty report to flag administration"),
        ("PSC-PORT", "port authority casualty notice", 12,
         "notice to port authority at next port"),
    ],
    "GROUNDING": [
        ("BD-DOS", "MSO casualty inquiry provisions", 24,
         "casualty report to flag administration"),
    ],
    "FIRE": [
        ("BD-DOS", "MSO casualty inquiry provisions", 24,
         "casualty report to flag administration"),
    ],
    "DEATH": [
        ("BD-DOS", "MSO casualty / crew death reporting", 24,
         "report of death or serious injury"),
    ],
    "INJURY": [
        ("BD-DOS", "MSO casualty / crew injury reporting", 24,
         "report of serious injury"),
    ],
    "CYBER": [
        ("BD-DOS", "IMO MSC.428(98) / MSC-FAL.1/Circ.3 cyber incident reporting", 72,
         "cyber incident report to flag administration"),
    ],
    "SECURITY": [
        ("BD-DOS", "ISPS Code A/5.9 security incident reporting", 24,
         "security incident report"),
    ],
    "MACHINERY": [],
    "CARGO": [],
    "EXPLOSION": [
        ("BD-DOS", "MSO casualty inquiry provisions", 24,
         "casualty report to flag administration"),
    ],
}

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Notification:
    id: str
    incident_id: str
    authority_id: str
    requirement_provision_id: str
    basis: str
    deadline: datetime
    sent_at: Optional[datetime] = None
    status: str = "PENDING"        # PENDING|SENT|ACKNOWLEDGED|OVERDUE

    def refresh_status(self, now: Optional[datetime] = None) -> str:
        now = now or _now()
        if self.status in ("SENT", "ACKNOWLEDGED"):
            return self.status
        self.status = "OVERDUE" if now > self.deadline else "PENDING"
        return self.status

    @property
    def hours_remaining(self) -> float:
        return (self.deadline - _now()).total_seconds() / 3600


@dataclass
class Incident:
    id: str
    company_id: str
    vessel_id: Optional[str]
    incident_type: str
    occurred_at: datetime
    location: dict = field(default_factory=dict)
    severity: str = "MEDIUM"
    description: str = ""
    status: str = "OPEN"           # OPEN|NOTIFIED|INVESTIGATING|CLOSED
    notifications: list[Notification] = field(default_factory=list)
    corrective_actions: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "company_id": self.company_id, "vessel_id": self.vessel_id,
            "incident_type": self.incident_type,
            "occurred_at": self.occurred_at.isoformat(),
            "location": self.location, "severity": self.severity,
            "description": self.description, "status": self.status,
            "notifications": [
                {**{k: getattr(n, k) for k in
                    ("id", "authority_id", "requirement_provision_id", "basis",
                     "status", "sent_at")},
                 "deadline": n.deadline.isoformat(),
                 "hours_remaining": round(n.hours_remaining, 1)}
                for n in self.notifications],
            "corrective_actions": self.corrective_actions,
            "compliance_posture": self.posture(),
        }

    def posture(self, now: Optional[datetime] = None) -> str:
        statuses = [n.refresh_status(now) for n in self.notifications]
        if "OVERDUE" in statuses:
            return "RED"
        if any(n.status == "PENDING" and n.hours_remaining < 6 for n in self.notifications):
            return "YELLOW"
        if not statuses or all(s in ("SENT", "ACKNOWLEDGED") for s in statuses):
            return "GREEN"
        return "YELLOW"


class IncidentRegistry:
    def __init__(self):
        self.incidents: dict[str, Incident] = {}

    def report(self, *, incident_id: str, company_id: str, incident_type: str,
               occurred_at: datetime, vessel_id: Optional[str] = None,
               location: Optional[dict] = None, severity: str = "MEDIUM",
               description: str = "") -> Incident:
        incident = Incident(
            id=incident_id, company_id=company_id, vessel_id=vessel_id,
            incident_type=incident_type.upper(), occurred_at=occurred_at,
            location=location or {}, severity=severity, description=description)

        for n, (authority, provision, hours, basis) in enumerate(
                NOTIFICATION_RULES.get(incident.incident_type, []), 1):
            incident.notifications.append(Notification(
                id=f"{incident_id}-N{n}", incident_id=incident_id,
                authority_id=authority, requirement_provision_id=provision,
                basis=basis, deadline=occurred_at + timedelta(hours=hours)))

        incident.corrective_actions.append({
            "id": f"{incident_id}-CA1", "action": "root-cause analysis + corrective plan",
            "status": "OPEN", "due_date": (occurred_at + timedelta(days=14)).date().isoformat(),
        })
        self.incidents[incident_id] = incident
        return incident

    def mark_sent(self, incident_id: str, notification_id: str) -> Notification:
        incident = self.incidents[incident_id]
        for n in incident.notifications:
            if n.id == notification_id:
                n.sent_at = _now()
                n.status = "SENT"
                if all(x.refresh_status() in ("SENT", "ACKNOWLEDGED")
                       for x in incident.notifications):
                    incident.status = "NOTIFIED"
                return n
        raise KeyError(f"notification {notification_id} not found")

    def list(self, company_id: Optional[str] = None) -> list[Incident]:
        items = [i for i in self.incidents.values()
                 if company_id is None or i.company_id == company_id]
        return sorted(items, key=lambda i: i.occurred_at, reverse=True)

    def overdue(self) -> list[tuple[Incident, Notification]]:
        out = []
        for incident in self.incidents.values():
            for n in incident.notifications:
                if n.refresh_status() == "OVERDUE":
                    out.append((incident, n))
        return out
