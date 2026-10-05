"""Demo operations world — incidents, liability, cyber, yard (P4/P5).

Real module logic over demo records; statuses are computed, never hard-coded.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..engine.cyber import assess_cyber
from ..engine.incident import IncidentRegistry
from ..engine.liability import InsurancePolicy, assess_liability
from ..engine.yard import ConstructionSurvey, DesignApproval, WorkPermit, permit_risk, project_readiness
from . import fleet, seed


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_incidents() -> IncidentRegistry:
    reg = IncidentRegistry()
    reg.report(incident_id="INC-2026-001", company_id=seed.COMPANY["id"],
               vessel_id=seed.VESSEL["id"], incident_type="POLLUTION",
               occurred_at=_now() - timedelta(hours=3),
               location={"zone_type": "TERRITORIAL", "coastal_state": "BD",
                         "lat": 22.15, "lon": 91.42},
               severity="HIGH",
               description="Bilge discharge during bunkering ops, contained, no shoreline impact.")
    reg.report(incident_id="INC-2026-002", company_id=fleet.COMPANY_GREEN["id"],
               vessel_id=fleet.VESSEL_GREEN["id"], incident_type="CYBER",
               occurred_at=_now() - timedelta(days=10),
               location={"zone_type": "HIGH_SEAS"},
               severity="MEDIUM",
               description="Ransomware attempt on crew-welfare network segment; contained by segmentation.")
    for n in reg.incidents["INC-2026-002"].notifications:
        reg.mark_sent("INC-2026-002", n.id)
    reg.report(incident_id="INC-2026-003", company_id=fleet.COMPANY_YELLOW["id"],
               vessel_id=fleet.VESSEL_YELLOW["id"], incident_type="COLLISION",
               occurred_at=_now() - timedelta(hours=2),
               location={"zone_type": "INTERNAL_WATERS", "coastal_state": "BD"},
               severity="LOW",
               description="Minor contact with berth fender during berthing; no damage beyond paintwork.")
    return reg


LIABILITY_POLICIES = {
    seed.VESSEL["id"]: [
        InsurancePolicy("ip-001", "VESSEL", seed.VESSEL["id"], "P&I", "Bangladesh P&I Club",
                        "PIC-2025-0441", seed.EVAL_DATE - timedelta(days=200),
                        seed.EVAL_DATE + timedelta(days=800), 500_000_000),
        InsurancePolicy("ip-002", "VESSEL", seed.VESSEL["id"], "H&M", "Sadharan Bima",
                        "HM-2024-118", seed.EVAL_DATE - timedelta(days=700),
                        seed.EVAL_DATE + timedelta(days=25), 25_000_000),   # expiring -> WATCH
    ],
    fleet.VESSEL_GREEN["id"]: [
        InsurancePolicy("ip-101", "VESSEL", fleet.VESSEL_GREEN["id"], "P&I", "Bangladesh P&I Club",
                        "PIC-2025-0871", seed.EVAL_DATE - timedelta(days=150),
                        seed.EVAL_DATE + timedelta(days=900), 750_000_000),
        InsurancePolicy("ip-102", "VESSEL", fleet.VESSEL_GREEN["id"], "H&M", "Sadharan Bima",
                        "HM-2025-331", seed.EVAL_DATE - timedelta(days=120),
                        seed.EVAL_DATE + timedelta(days=1000), 40_000_000),
    ],
    fleet.VESSEL_YELLOW["id"]: [
        InsurancePolicy("ip-201", "VESSEL", fleet.VESSEL_YELLOW["id"], "P&I", "Bangladesh P&I Club",
                        "PIC-2024-219", seed.EVAL_DATE - timedelta(days=500),
                        seed.EVAL_DATE + timedelta(days=25), 300_000_000),  # expiring -> WATCH
        InsurancePolicy("ip-202", "VESSEL", fleet.VESSEL_YELLOW["id"], "H&M", "Sadharan Bima",
                        "HM-2024-220", seed.EVAL_DATE - timedelta(days=400),
                        seed.EVAL_DATE + timedelta(days=800), 18_000_000),
    ],
    # SHITALAKSHYA: no P&I on file + expired H&M -> ELEVATED signals
    fleet.VESSEL_BLACK["id"]: [
        InsurancePolicy("ip-301", "VESSEL", fleet.VESSEL_BLACK["id"], "H&M", "Sadharan Bima",
                        "HM-2022-771", seed.EVAL_DATE - timedelta(days=1200),
                        seed.EVAL_DATE - timedelta(days=60), 12_000_000),
    ],
}


def build_liability_reports() -> list[dict]:
    return [assess_liability(vessel_id=vid, policies=pol,
                             as_of=seed.EVAL_DATE).as_dict()
            for vid, pol in LIABILITY_POLICIES.items()]


CYBER_STATUS = {
    "co-demo-001": {"ID-1": "GREEN", "PR-2": "GREEN", "PR-3": "YELLOW",
                    "DE-4": "YELLOW", "RS-5": "GREEN", "RC-6": "YELLOW",
                    "GV-7": "GREEN", "NAT-8": "YELLOW"},
    "co-demo-002": {"ID-1": "GREEN", "PR-2": "GREEN", "PR-3": "GREEN",
                    "DE-4": "GREEN", "RS-5": "GREEN", "RC-6": "GREEN",
                    "GV-7": "GREEN", "NAT-8": "YELLOW"},
    "co-demo-003": {"ID-1": "GREEN", "PR-2": "YELLOW", "PR-3": "YELLOW",
                    "DE-4": "YELLOW", "RS-5": "YELLOW", "RC-6": "BLACK",
                    "GV-7": "YELLOW", "NAT-8": "YELLOW"},
    "co-demo-004": {"ID-1": "YELLOW", "PR-2": "RED", "PR-3": "RED",
                    "DE-4": "RED", "RS-5": "YELLOW", "RC-6": "BLACK",
                    "GV-7": "YELLOW", "NAT-8": "YELLOW"},
}


def build_cyber_postures() -> list[dict]:
    names = {"co-demo-001": seed.COMPANY["name"], "co-demo-002": fleet.COMPANY_GREEN["name"],
             "co-demo-003": fleet.COMPANY_YELLOW["name"], "co-demo-004": fleet.COMPANY_BLACK["name"]}
    out = []
    for company_id, statuses in CYBER_STATUS.items():
        posture = assess_cyber("COMPANY", company_id, statuses)
        d = posture.as_dict()
        d["name"] = names[company_id]
        out.append(d)
    return out


def build_yard() -> dict:
    approvals = [
        DesignApproval("HULL", "APPROVED"), DesignApproval("STABILITY", "APPROVED"),
        DesignApproval("MACHINERY", "APPROVED"), DesignApproval("ELECTRICAL", "APPROVED"),
        DesignApproval("FIRE", "APPROVED"), DesignApproval("LIFESAVING", "APPROVED"),
        DesignApproval("NAVIGATION", "APPROVED"), DesignApproval("RADIO", "CONDITIONAL"),
    ]
    surveys = [
        ConstructionSurvey("KEEL_LAYING", "SATISFACTORY", "2025-11-02"),
        ConstructionSurvey("HULL", "SATISFACTORY", "2026-03-18"),
        ConstructionSurvey("WELDING", "SATISFACTORY", "2026-04-02"),
        ConstructionSurvey("MACHINERY", "DEFICIENCY", "2026-08-21"),
    ]
    permits = [
        WorkPermit("wp-001", "HOT_WORK", _now() - timedelta(hours=5),
                   _now() + timedelta(hours=1), vessel_id="v-demo-001", facility_id="yard-01"),
        WorkPermit("wp-002", "CONFINED_SPACE", _now() - timedelta(hours=2),
                   _now() + timedelta(hours=6), vessel_id="v-demo-003", facility_id="yard-01"),
        WorkPermit("wp-003", "HOT_WORK", _now() - timedelta(days=2),
                   _now() - timedelta(hours=6), vessel_id="v-demo-004", facility_id="yard-01"),
    ]
    readiness = project_readiness(approvals, surveys)
    risk = permit_risk(permits)
    return {
        "project": {"project_id": "SP-2026-01", "hull_no": "BKI-1180",
                    "project_name": "52k DWT Bulk Carrier", "phase": "CONSTRUCTION",
                    "intended_flag": "BD",
                    "readiness": {"status": readiness["status"].value,
                                  "reason": readiness["reason"]},
                    "design_approvals": [{"plan_type": a.plan_type, "status": a.status}
                                         for a in approvals],
                    "surveys": [{"survey_type": s.survey_type, "result": s.result,
                                 "survey_date": s.survey_date} for s in surveys]},
        "permits": risk,
        "disclaimer": "shipyard hot-work / confined-space permits are hard gates — "
                      "work without a valid permit is a stop-work condition",
    }
