#!/usr/bin/env python3
"""Bake real engine output into frontend/demo_data.json.

The frontend prefers the live API; when it is not reachable (static hosting
on Vercel / GitHub Pages / offline), it falls back to this file. Every value
here is produced by the real engine — nothing is hand-written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mris.corpus import RULES_DIR, load_manifest, load_rules            # noqa: E402
from mris.demo import fleet as fleet_seed                               # noqa: E402
from mris.demo import seed                                              # noqa: E402
from mris.demo.review_seed import build_review_world                   # noqa: E402
from mris.demo.operations import (build_cyber_postures, build_incidents,
                                  build_liability_reports, build_yard)   # noqa: E402
from mris.demo.runner import assess, assess_fleet                       # noqa: E402
from mris.engine import Constraint, Layer, RuleCandidate, resolve_voyage  # noqa: E402
from mris.engine.lca1 import Leg                                        # noqa: E402
from mris.engine.state_participation import load_state_participation     # noqa: E402
from mris.ilrmf import EvalContext, parse_rule_spec                     # noqa: E402


def compliance_payload(company, vessel, crew, evidence, app_extra=None):
    ctx = fleet_seed.build_context(vessel, crew, evidence, company)
    app_facts = {"flag": "BD", "operation": "SEA_VOYAGE",
                 "ship_type": vessel.get("ship_type", "CARGO"),
                 "zone_type": "TERRITORIAL", "coastal_state": "BD", "port": "CHITTAGONG"}
    if app_extra:
        app_facts.update(app_extra)
    result = assess(ctx, company=company, vessel=vessel, applicability_facts=app_facts)
    return result.as_dict()


def main() -> None:
    manifest = load_manifest()
    rules = load_rules()

    fleet = assess_fleet()
    compliance = {}
    compliance[seed.VESSEL["imo_number"]] = compliance_payload(
        seed.COMPANY, seed.VESSEL, seed.CREW, seed.EVIDENCE, seed.APPLICABILITY_FACTS)
    for entry in fleet_seed.FLEET:
        if "seed_module" in entry:
            continue
        compliance[entry["vessel"]["imo_number"]] = compliance_payload(
            entry["company"], entry["vessel"], entry["crew"], entry["evidence"])

    # voyage sample (LCA-1) — same shape as /v1/voyages/obligation-preview
    legs = [Leg(seq=1, zone_type="INTERNAL_WATERS", coastal_state="BD"),
            Leg(seq=2, zone_type="TERRITORIAL", coastal_state="BD", port="CHITTAGONG")]
    candidates = [RuleCandidate(
        rule_id="IMO-CONV-SOLAS-1974-MANNING-FLOOR", layer=Layer.L1_INTL,
        dimension="manning_level", requirement="STCW-safe manning floor",
        provision_ids=["IMO-CONV-STCW-1978-CHVIII-REG01"],
        rule_version_id="rv-imo-manning-v1", legal_version_id="lv-stcw-1978-current",
        constraint=Constraint.min(3))]
    for rule_id, spec in rules.items():
        candidates.append(RuleCandidate(
            rule_id=rule_id, layer=Layer.L2_FLAG, dimension=spec.domain.lower(),
            requirement=spec.outcome.get("contract_requirement", spec.domain),
            provision_ids=[spec.legal_source["provision_id"]],
            rule_version_id=f"{rule_id}-v{spec.rule_version}",
            legal_version_id=spec.legal_source.get("legal_version_id", "unversioned"),
            applicability={"flag": ["BD"]}, spec=spec))
    voyage = resolve_voyage(legs, candidates, vessel_flag="BD", domestic=True,
                            as_of=seed.EVAL_DATE)

    rule_texts = {rid: (RULES_DIR / f"{rid}.yaml").read_text(encoding="utf-8")
                  for rid in rules}

    # legal-review world (queue + audit + ingestion) for the static console
    pipeline, queue, audit = build_review_world()

    _vessel_names = {seed.VESSEL["id"]: seed.VESSEL["name"]}
    _vessel_imos = {seed.VESSEL["id"]: seed.VESSEL["imo_number"]}
    for _e in fleet_seed.FLEET:
        if "seed_module" in _e:
            continue
        _vessel_names[_e["vessel"]["id"]] = _e["vessel"]["name"]
        _vessel_imos[_e["vessel"]["id"]] = _e["vessel"]["imo_number"]

    data = {
        "generated_at": seed.EVAL_DATE.isoformat(),
        "as_of_date": seed.EVAL_DATE.isoformat(),
        "fleet": {"as_of_date": seed.EVAL_DATE.isoformat(),
                  "fleet_status_counts": {
                      s: sum(1 for e in fleet if e["status"] == s)
                      for s in ("GREEN", "YELLOW", "RED", "BLACK")},
                  "vessels": fleet,
                  "note": "demo fleet; statuses computed by ILRMF-DSL rules over demo evidence"},
        "compliance": compliance,
        "instruments": {"bangladesh": manifest["instruments"],
                        "international": manifest["international_instruments"]},
        "impacts": {"open_verification_items": manifest["open_items_register"],
                    "sla": "official publication -> customer alert <= 72h for high-impact changes"},
        "rules": rule_texts,
        "review": {"pending": queue.pending_count(),
                   "items": [i.as_dict() for i in queue.list()],
                   "gates": ["EXTRACTED_BY_AI -> REVIEWED -> VERIFIED_AGAINST_GAZETTE",
                             "two-person: verifier must differ from reviewer",
                             "only VERIFIED provisions feed live compliance (fail-closed)"],
                   "two_person_rule": True},
        "audit": {"chain_valid": audit.verify_chain()[0],
                  "broken_at_entry": audit.verify_chain()[1],
                  "entries": audit.entries},
        "ingestion": pipeline.status(),
        "treaty": {"flag": "BD", "as_of": seed.EVAL_DATE.isoformat(),
                   "rows": load_state_participation().treaty_status("BD", seed.EVAL_DATE)},
        "ops": {
            "incidents": {"incidents": [i.as_dict() for i in build_incidents().list()],
                          "overdue": [{"incident_id": i.id, "notification_id": n.id,
                                       "authority_id": n.authority_id, "basis": n.basis,
                                       "deadline": n.deadline.isoformat()}
                                      for i, n in build_incidents().overdue()]},
            "cyber": {"postures": build_cyber_postures(),
                      "national_note": "BD ICT Act 2006 / Cyber Security Act 2023 mapping is an "
                                       "open verification item"},
            "yard": build_yard(),
            "liability": [dict(name=_vessel_names.get(r["vessel_id"], ""),
                               imo=_vessel_imos.get(r["vessel_id"], ""), **r)
                          for r in build_liability_reports()],
        },
        "voyageSample": {"overall_status": voyage.overall_status.value,
                         "conflict_items": voyage.conflict_items,
                         "drill_down": voyage.drill_down,
                         "algorithm": "LCA-1", "legal_review_sla_hours": 48},
    }

    out = ROOT / "frontend" / "demo_data.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                   encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB, {len(fleet)} vessels, "
          f"{len(rule_texts)} rule specs)")


if __name__ == "__main__":
    main()
