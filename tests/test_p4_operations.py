"""P4/P5 tests: incident notifications, liability advisory, cyber posture, yard readiness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mris.engine import (ConstructionSurvey, DesignApproval, InsurancePolicy,
                         IncidentRegistry, Status, WorkPermit, assess_cyber,
                         assess_liability, permit_risk, project_readiness)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.date()


# ---------------------------------------------------------------------------
# incidents: deterministic notification deadlines
# ---------------------------------------------------------------------------

def test_pollution_notification_deadlines():
    reg = IncidentRegistry()
    inc = reg.report(incident_id="I1", company_id="co1", incident_type="POLLUTION",
                     occurred_at=NOW - timedelta(hours=3))
    assert len(inc.notifications) == 3
    # 1h initial report is overdue after 3h; 24h and 30d still pending
    statuses = [n.refresh_status(NOW) for n in inc.notifications]
    assert statuses[0] == "OVERDUE"
    assert statuses[1] == "PENDING"
    assert inc.posture(NOW) == "RED"

    reg.mark_sent("I1", inc.notifications[0].id)
    assert inc.notifications[0].status == "SENT"
    assert inc.posture(NOW) == "YELLOW"          # others still pending

    for n in inc.notifications:
        reg.mark_sent("I1", n.id)
    assert inc.posture(NOW) == "GREEN" and inc.status == "NOTIFIED"


def test_notification_deadline_math():
    reg = IncidentRegistry()
    inc = reg.report(incident_id="I2", company_id="co1", incident_type="COLLISION",
                     occurred_at=NOW)
    by_authority = {n.authority_id: n for n in inc.notifications}
    assert by_authority["BD-DOS"].deadline == NOW + timedelta(hours=24)
    assert by_authority["PSC-PORT"].deadline == NOW + timedelta(hours=12)

    inc2 = reg.report(incident_id="I3", company_id="co1", incident_type="MACHINERY",
                      occurred_at=NOW)
    assert inc2.notifications == []           # no reportable notifications


# ---------------------------------------------------------------------------
# liability: advisory only, never weakens statutory
# ---------------------------------------------------------------------------

def test_liability_flags():
    policies = [
        InsurancePolicy("p1", "VESSEL", "v1", "P&I", "Club", "PIC-1",
                        TODAY - timedelta(days=100), TODAY + timedelta(days=20)),   # expiring
        InsurancePolicy("p2", "VESSEL", "v1", "H&M", "Insurer", "HM-1",
                        TODAY - timedelta(days=800), TODAY - timedelta(days=10)),   # expired
    ]
    rep = assess_liability("v1", policies, as_of=TODAY)
    flags = {(f.exposure_type, f.flag) for f in rep.flags}
    assert ("P&I", "WATCH") in flags                       # expiring within 30d
    assert ("H&M", "ELEVATED") in flags                    # expired
    assert rep.risk_level == "ELEVATED"
    assert all(f.advisory for f in rep.flags)              # Principle 15

    # missing P&I cover entirely => ELEVATED financial-security signal
    rep2 = assess_liability("v2", [], as_of=TODAY)
    assert {(f.exposure_type, f.flag) for f in rep2.flags} == {("P&I", "ELEVATED"), ("H&M", "ELEVATED")}

    # clean covers -> INFO only
    rep3 = assess_liability("v3", [
        InsurancePolicy("p3", "VESSEL", "v3", "P&I", "Club", "PIC-3",
                        TODAY - timedelta(days=50), TODAY + timedelta(days=400)),
        InsurancePolicy("p4", "VESSEL", "v3", "H&M", "Insurer", "HM-3",
                        TODAY - timedelta(days=50), TODAY + timedelta(days=400)),
    ], as_of=TODAY)
    assert rep3.risk_level == "INFO"


# ---------------------------------------------------------------------------
# cyber: fail-closed rollup
# ---------------------------------------------------------------------------

def test_cyber_posture_rollup():
    full = {"ID-1": "GREEN", "PR-2": "GREEN", "PR-3": "GREEN", "DE-4": "GREEN",
            "RS-5": "GREEN", "RC-6": "GREEN", "GV-7": "GREEN", "NAT-8": "YELLOW"}
    assert assess_cyber("COMPANY", "co1", full).overall is Status.YELLOW

    gap = {**full, "DE-4": "RED"}
    assert assess_cyber("COMPANY", "co1", gap).overall is Status.RED

    # missing assessment data => BLACK (fail-closed)
    assert assess_cyber("COMPANY", "co1", {}).overall is Status.BLACK

    # unparseable status => BLACK
    assert assess_cyber("COMPANY", "co1", {"ID-1": "???"}).overall is Status.BLACK


# ---------------------------------------------------------------------------
# yard: readiness ladder + permit exposure
# ---------------------------------------------------------------------------

def test_project_readiness_ladder():
    ok = [DesignApproval("HULL", "APPROVED"), DesignApproval("FIRE", "APPROVED")]
    ok_surveys = [ConstructionSurvey("HULL", "SATISFACTORY")]
    assert project_readiness(ok, ok_surveys)["status"] is Status.GREEN

    assert project_readiness([], [])["status"] is Status.BLACK
    assert project_readiness([DesignApproval("HULL", "REJECTED")], [])["status"] is Status.BLACK
    assert project_readiness([DesignApproval("HULL", "APPROVED"),
                              DesignApproval("FIRE", "SUBMITTED")], [])["status"] is Status.RED
    assert project_readiness(ok, [ConstructionSurvey("MACHINERY", "DEFICIENCY")])["status"] is Status.YELLOW
    assert project_readiness(ok, [ConstructionSurvey("MACHINERY", "HOLD")])["status"] is Status.BLACK


def test_permit_risk_expired_but_open():
    permits = [
        WorkPermit("wp1", "HOT_WORK", NOW - timedelta(hours=8), NOW - timedelta(hours=2)),
        WorkPermit("wp2", "CONFINED_SPACE", NOW - timedelta(hours=1), NOW + timedelta(hours=5)),
        WorkPermit("wp3", "ALOFT", NOW - timedelta(hours=1), NOW + timedelta(hours=3), status="SUSPENDED"),
    ]
    risk = permit_risk(permits, now=NOW)
    assert risk["risk"] == "ELEVATED"
    assert [p["id"] for p in risk["expired_but_open"]] == ["wp1"]
    assert risk["active"] == ["wp2"] and risk["suspended"] == ["wp3"]

    clean = permit_risk([permits[1]], now=NOW)
    assert clean["risk"] == "INFO"
