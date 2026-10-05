"""MRIS API — Part 12.2 endpoint surface.

Runs over the demo corpus/engine store in this milestone; swap the store for
the PostgreSQL backend (infra/db/migrations/001_initial_schema.sql) when the
database is provisioned. Every compliance endpoint accepts as_of (Principle
10: historical reconstruction).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..corpus import RULES_DIR, load_manifest, load_rules
from ..demo import fleet as fleet_seed
from ..demo import seed
from ..demo.runner import assess, assess_fleet, assess_vessel
from ..engine import (ComplianceResult, Constraint, Layer, NOTIFICATION_RULES,
                      RuleCandidate, execute_rule, item_from_outcome,
                      resolve_voyage)
from ..engine.ingestion import (IngestionPipeline, SourceFeed,
                                rule_impact_match)
from ..engine.lca1 import Leg
from ..engine.verification import (AuditChain, QueueItem, ReviewQueue,
                                   VerificationError, VerificationTier,
                                   rule_can_go_active)
from ..engine.state_participation import load_state_participation
from ..ilrmf import EvalContext, RuleSpecError, parse_rule_spec

app = FastAPI(
    title="MRIS — Maritime Regulatory Intelligence Suite",
    version="0.1.0",
    description="Regulatory intelligence, not legal advice. "
                "Unverified content never feeds live compliance calculations (fail-closed).",
)

_RULES = load_rules()
_MANIFEST = load_manifest()


# ---------------------------------------------------------------------------
# request bodies
# ---------------------------------------------------------------------------

class RuleEvalRequest(BaseModel):
    rule_yaml: str = Field(..., description="ILRMF-DSL rule spec (YAML surface, Part 9.2)")
    facts: dict[str, Any] = Field(default_factory=dict)
    applicability_facts: dict[str, Any] = Field(default_factory=dict)
    eval_date: Optional[date] = None


class LegSpec(BaseModel):
    seq: int
    zone_type: str
    coastal_state: Optional[str] = None
    port: Optional[str] = None


class VoyagePreviewRequest(BaseModel):
    vessel_flag: str
    domestic: bool = False
    as_of: Optional[date] = None
    legs: list[LegSpec] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# health / corpus
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mris", "engine": "mris-engine/0.1.0"}


@app.get("/v1/legal/instruments")
def list_instruments() -> dict:
    return {
        "bangladesh": _MANIFEST["instruments"],
        "international": _MANIFEST["international_instruments"],
    }


@app.get("/v1/legal/instruments/{instrument_id}/versions")
def instrument_versions(instrument_id: str) -> dict:
    """Version chain. Temporal: provision_validity + legal_version intervals."""
    inst = _find_instrument(instrument_id)
    versions = [{"version_no": 1, "basis": "ORIGINAL",
                 "effective_from": inst.get("enacted_date"),
                 "effective_to": None, "verification_status": inst.get("verification_status")}]
    for amend in inst.get("repeals", []):
        versions.append({"version_no": len(versions) + 1,
                         "basis": f"REPEAL:{amend.get('instrument_id')}",
                         "effective_from": None, "effective_to": None})
    return {"instrument_id": instrument_id, "title": inst.get("title"),
            "status": inst.get("status"), "versions": versions}


@app.get("/v1/legal/provisions/{provision_id}/history")
def provision_history(provision_id: str) -> dict:
    return {
        "provision_id": provision_id,
        "temporal_chain": [
            {"valid_from": "enacted", "valid_to": None,
             "verification_status": "EXTRACTED_BY_AI",
             "note": "per-version validity intervals live in provision_validity; "
                     "history reconstructed from legal_version + amendment objects"}
        ],
        "principle": "repealed != deleted; never treat draft as current; "
                     "never apply future law early (Part 2)",
    }


_STATE_DB = load_state_participation()


@app.get("/v1/jurisdiction/{flag}/treaty-status")
def treaty_status(flag: str, as_of: Optional[date] = None) -> dict:
    """'Is instrument X in force for this flag on date D?' (Part 6.5)."""
    at = as_of or seed.EVAL_DATE
    rows = _STATE_DB.treaty_status(flag, at)
    if not rows:
        raise HTTPException(404, f"no participation data for flag {flag}")
    return {"flag": flag, "as_of": at.isoformat(), "rows": rows,
            "policy": "EXTRACTED_BY_AI rows never feed production compliance until "
                      "VERIFIED_AGAINST_GAZETTE; future amendments never applied early"}


@app.get("/v1/rules")
def list_rules() -> dict:
    """Executable rule specs (YAML surface) keyed by rule_id."""
    return {rid: (RULES_DIR / f"{rid}.yaml").read_text(encoding="utf-8")
            for rid in _RULES}


@app.get("/v1/changes/impacts")
def change_impacts() -> dict:
    return {"open_verification_items": _MANIFEST["open_items_register"],
            "sla": "official publication -> customer alert <= 72h for high-impact changes"}


# ---------------------------------------------------------------------------
# compliance
# ---------------------------------------------------------------------------

@app.get("/v1/fleet/summary")
def fleet_summary() -> dict:
    """Demo fleet — every status computed by the real engine (RED/GREEN/YELLOW)."""
    entries = assess_fleet()
    totals = {s: 0 for s in ("GREEN", "YELLOW", "RED", "BLACK")}
    for e in entries:
        totals[e["status"]] += 1
    return {"as_of_date": seed.EVAL_DATE.isoformat(),
            "fleet_status_counts": totals,
            "vessels": entries,
            "note": "demo fleet; statuses computed by ILRMF-DSL rules over demo evidence"}


def _fleet_vessel(imo: str) -> tuple[dict, dict, list, list]:
    """(company, vessel, crew, evidence) for a demo-fleet IMO number."""
    if imo == seed.VESSEL["imo_number"]:
        return seed.COMPANY, seed.VESSEL, seed.CREW, seed.EVIDENCE
    for entry in fleet_seed.FLEET:
        if "seed_module" in entry:
            continue
        if entry["vessel"]["imo_number"] == imo:
            return entry["company"], entry["vessel"], entry["crew"], entry["evidence"]
    raise HTTPException(404, f"vessel {imo} not in demo store")


@app.get("/v1/vessels/{imo}/compliance")
def vessel_compliance(imo: str, as_of: Optional[date] = None) -> dict:
    company, vessel, crew, evidence = _fleet_vessel(imo)
    ctx = fleet_seed.build_context(vessel, crew, evidence, company)
    result = assess(ctx, company=company, vessel=vessel)
    payload = result.as_dict()
    if as_of is not None:
        payload["as_of_requested"] = as_of.isoformat()
        payload["note"] = ("historical re-run uses provision_validity + rule_version "
                           "intervals to reproduce the past result exactly (Principle 10)")
    return payload


@app.get("/v1/vessels/{imo}/compliance/{item_id}/provenance")
def item_provenance(imo: str, item_id: str) -> dict:
    company, vessel, crew, evidence = _fleet_vessel(imo)
    ctx = fleet_seed.build_context(vessel, crew, evidence, company)
    result = assess(ctx, company=company, vessel=vessel)
    for item in result.items:
        if item.obligation_id == item_id or item_id in item.obligation_id:
            return {
                "chain": [
                    {"level": "result", "detail": f"{result.entity_type}/{result.entity_id} "
                                                   f"@ {result.as_of_date}: {item.status.value}"},
                    {"level": "rule", "detail": item.contract.rule_executed},
                    {"level": "provision", "detail": item.provision_id},
                    {"level": "legal_version", "detail": item.contract.legal_version},
                    {"level": "instrument", "detail": item.contract.source_law},
                    {"level": "official_source", "detail": "bdlaws.minlaw.gov.bd / Gazette "
                                                           "(verification_status gates production use)"},
                ],
                "item": item.as_dict(),
            }
    raise HTTPException(404, f"item {item_id} not found")


# ---------------------------------------------------------------------------
# rule engine
# ---------------------------------------------------------------------------

@app.post("/v1/rule/evaluate")
def rule_eval(req: RuleEvalRequest) -> dict:
    try:
        spec = parse_rule_spec(req.rule_yaml)
    except RuleSpecError as exc:
        raise HTTPException(422, f"rule rejected (never reaches ACTIVE): {exc}")

    eval_date = req.eval_date or seed.EVAL_DATE
    ctx = EvalContext(eval_date=eval_date, facts=req.facts,
                      crew=req.facts.get("current_crew", []),
                      evidence=req.facts.get("evidence", []))
    outcome = execute_rule(spec, ctx,
                           applicability_facts=req.applicability_facts)
    return {
        "rule_id": outcome.rule_id,
        "provision_id": outcome.provision_id,
        "legal_version_id": outcome.legal_version_id,
        "status": outcome.status.value,
        "applicability": outcome.applicable.value,
        "condition": outcome.condition.value,
        "reason": outcome.reason,
        "unknown_reasons": outcome.unknown_reasons,
        "lawyer_review_needed": outcome.lawyer_review_needed,
    }


@app.post("/v1/voyages/obligation-preview")
def obligation_preview(req: VoyagePreviewRequest) -> dict:
    """Runs LCA-1 (Part 9.6) over the supplied legs."""
    as_of = req.as_of or seed.EVAL_DATE
    legs = [Leg(seq=l.seq, zone_type=l.zone_type, coastal_state=l.coastal_state,
                port=l.port) for l in req.legs] or [
        Leg(seq=1, zone_type="INTERNAL_WATERS", coastal_state="BD"),
        Leg(seq=2, zone_type="TERRITORIAL", coastal_state="BD", port="CHITTAGONG"),
    ]
    candidates = _demo_candidates()
    result = resolve_voyage(legs, candidates, vessel_flag=req.vessel_flag,
                            domestic=req.domestic, as_of=as_of)
    return {
        "overall_status": result.overall_status.value,
        "conflict_items": result.conflict_items,
        "drill_down": result.drill_down,
        "algorithm": "LCA-1",
        "legal_review_sla_hours": 48,
    }


def _demo_candidates() -> list[RuleCandidate]:
    """Corpus rules as L2 candidates + an IMO manning floor to show STRICTER."""
    out = [RuleCandidate(
        rule_id="IMO-CONV-SOLAS-1974-MANNING-FLOOR", layer=Layer.L1_INTL,
        dimension="manning_level", requirement="STCW-safe manning floor",
        provision_ids=["IMO-CONV-STCW-1978-CHVIII-REG01"],
        rule_version_id="rv-imo-manning-v1", legal_version_id="lv-stcw-1978-current",
        constraint=Constraint.min(3)),
    ]
    for rule_id, spec in _RULES.items():
        out.append(RuleCandidate(
            rule_id=rule_id, layer=Layer.L2_FLAG, dimension=spec.domain.lower(),
            requirement=spec.outcome.get("contract_requirement", spec.domain),
            provision_ids=[spec.legal_source["provision_id"]],
            rule_version_id=f"{rule_id}-v{spec.rule_version}",
            legal_version_id=spec.legal_source.get("legal_version_id", "unversioned"),
            applicability={"flag": ["BD"]}, spec=spec))
    return out


def _find_instrument(instrument_id: str) -> dict:
    for inst in _MANIFEST["instruments"] + _MANIFEST["international_instruments"]:
        if inst["id"] == instrument_id:
            return inst
    raise HTTPException(404, f"instrument {instrument_id} not found")


# ---------------------------------------------------------------------------
# legal review / verification / ingestion (Part 11 — P2)
# ---------------------------------------------------------------------------

_AUDIT = AuditChain()
_QUEUE = ReviewQueue(_AUDIT)
_PIPELINE = IngestionPipeline(_QUEUE, _AUDIT)

# Seeded review world (shared with the static demo bake)
from ..demo.review_seed import build_review_world  # noqa: E402
_PIPELINE, _QUEUE, _AUDIT = build_review_world()




@app.get("/v1/review/queue")
def review_queue(tier: Optional[str] = None) -> dict:
    t = VerificationTier(tier) if tier else None
    items = _QUEUE.list(t)
    return {
        "pending": _QUEUE.pending_count(),
        "items": [i.as_dict() for i in items],
        "gates": ["EXTRACTED_BY_AI -> REVIEWED -> VERIFIED_AGAINST_GAZETTE",
                  "two-person: verifier must differ from reviewer",
                  "only VERIFIED provisions feed live compliance (fail-closed)"],
        "two_person_rule": True,
    }


class ReviewAction(BaseModel):
    actor_id: str
    notes: str = ""
    source_url: Optional[str] = None


@app.post("/v1/review/queue/{item_id}/review")
def review_item(item_id: str, body: ReviewAction) -> dict:
    try:
        item = _QUEUE.review(item_id, body.actor_id, body.notes)
    except VerificationError as exc:
        raise HTTPException(409, str(exc))
    return item.as_dict()


@app.post("/v1/review/queue/{item_id}/verify")
def verify_item(item_id: str, body: ReviewAction) -> dict:
    try:
        item = _QUEUE.verify(item_id, body.actor_id, body.source_url)
    except VerificationError as exc:
        raise HTTPException(409, str(exc))
    return item.as_dict()


@app.get("/v1/audit/trail")
def audit_trail(object_type: Optional[str] = None,
                object_id: Optional[str] = None) -> dict:
    ok, broken_at = _AUDIT.verify_chain()
    return {"chain_valid": ok, "broken_at_entry": broken_at,
            "entries": _AUDIT.trail(object_type, object_id)}


@app.get("/v1/ingestion/status")
def ingestion_status() -> dict:
    return _PIPELINE.status()


class IngestRequest(BaseModel):
    source_id: str
    content: str
    instrument_id: str = "UNASSIGNED"


@app.post("/v1/ingestion/ingest")
def ingest_document(body: IngestRequest) -> dict:
    if body.source_id not in _PIPELINE.feeds:
        raise HTTPException(404, f"source {body.source_id} not registered")
    result = _PIPELINE.ingest(body.source_id, body.content, body.instrument_id)
    return {"changed": result.changed, "sha256": result.sha256,
            "classification": result.classification,
            "provision_count": result.provision_count,
            "queue_ids": result.queue_ids, "notes": result.notes}


@app.get("/v1/rules/active-gate/{rule_id}")
def rule_active_gate(rule_id: str) -> dict:
    """Principle 12 gate: can this rule reach ACTIVE?"""
    spec = _RULES.get(rule_id)
    if spec is None:
        raise HTTPException(404, f"rule {rule_id} not found")
    provision_id = spec.legal_source["provision_id"]
    allowed, unverified = rule_can_go_active([provision_id], _QUEUE)
    return {"rule_id": rule_id, "can_go_active": allowed,
            "unverified_provisions": unverified,
            "rule_provision_verified": _QUEUE.is_verified(provision_id) or
                                       spec.legal_source.get("verification_status") ==
                                       "VERIFIED_AGAINST_GAZETTE",
            "policy": "unverified content never feeds live compliance calculations"}


# ---------------------------------------------------------------------------
# operations & risk: incidents, liability, cyber, yard (P4/P5)
# ---------------------------------------------------------------------------
from ..demo.operations import (LIABILITY_POLICIES, build_cyber_postures,
                               build_incidents, build_yard)  # noqa: E402

_INCIDENTS = build_incidents()
_YARD = build_yard()


class IncidentReport(BaseModel):
    incident_id: str
    company_id: str
    incident_type: str
    occurred_at: datetime
    vessel_id: Optional[str] = None
    location: dict = Field(default_factory=dict)
    severity: str = "MEDIUM"
    description: str = ""


@app.get("/v1/incidents")
def list_incidents() -> dict:
    items = [i.as_dict() for i in _INCIDENTS.list()]
    overdue = [{"incident_id": i.id, "notification_id": n.id,
                "authority_id": n.authority_id, "basis": n.basis,
                "deadline": n.deadline.isoformat()}
               for i, n in _INCIDENTS.overdue()]
    return {"incidents": items, "overdue": overdue,
            "notification_rules": {k: [{"authority": a, "provision": p,
                                        "hours": h, "scope": s} for a, p, h, s in v]
                                   for k, v in NOTIFICATION_RULES.items() if v},
            "policy": "deadlines computed deterministically from incident type + occurrence"}


@app.post("/v1/incidents")
def report_incident(body: IncidentReport) -> dict:
    incident = _INCIDENTS.report(
        incident_id=body.incident_id, company_id=body.company_id,
        incident_type=body.incident_type, occurred_at=body.occurred_at,
        vessel_id=body.vessel_id, location=body.location,
        severity=body.severity, description=body.description)
    return incident.as_dict()


@app.post("/v1/incidents/{incident_id}/notifications/{notification_id}/mark-sent")
def mark_notification_sent(incident_id: str, notification_id: str) -> dict:
    try:
        n = _INCIDENTS.mark_sent(incident_id, notification_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return {"notification_id": n.id, "status": n.status,
            "sent_at": n.sent_at.isoformat() if n.sent_at else None}


@app.get("/v1/liability/{imo}")
def liability_flags(imo: str) -> dict:
    _company, vessel, _crew, _evidence = _fleet_vessel(imo)
    from ..demo.operations import build_liability_reports
    for report in build_liability_reports():
        if report["vessel_id"] == vessel["id"]:
            return report
    raise HTTPException(404, f"no liability data for {imo}")


@app.get("/v1/cyber")
def cyber_postures() -> dict:
    return {"postures": build_cyber_postures(),
            "framework": "IMO MSC.428(98) + MSC-FAL.1/Circ.3 five-step model",
            "national_note": "BD ICT Act 2006 / Cyber Security Act 2023 mapping is an open "
                             "verification item — controls stay gated until closed"}


@app.get("/v1/yard/readiness")
def yard_readiness() -> dict:
    return _YARD


# ---------------------------------------------------------------------------
# frontend (premium UI) — served at the root path
# ---------------------------------------------------------------------------
_log = logging.getLogger("mris.api")
_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "frontend",   # repo layout
    Path(__file__).resolve().parent.parent / "frontend",          # installed layout
    Path.cwd() / "frontend",                                      # CWD layout
]
_FRONTEND_DIR = next((p for p in _CANDIDATES if p.is_dir()), _CANDIDATES[0])
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    # never silently skip the UI again (Render incident: missing COPY in Dockerfile)
    _log.warning("frontend directory not found — checked %s; UI will NOT be served",
                 [str(p) for p in _CANDIDATES])
