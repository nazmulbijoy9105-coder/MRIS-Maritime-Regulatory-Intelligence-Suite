"""Demo runner: vessel assessments — the P1 exit-criteria exercise + fleet."""
from __future__ import annotations

from . import fleet, seed
from ..corpus import load_rules
from ..engine import ComplianceResult, Status, execute_rule, item_from_outcome
from ..engine.state_participation import load_state_participation

_SOURCE_TITLES = {
    "BD-ORD-MERCHANT-SHIPPING-1983-S082":
        "Bangladesh Merchant Shipping Ordinance, 1983 (Ord. XXVI of 1983), Section 82",
    "BD-ORD-MERCHANT-SHIPPING-1983-S335":
        "Bangladesh Merchant Shipping Ordinance, 1983 (Ord. XXVI of 1983), Section 335",
    "BD-ORD-MERCHANT-SHIPPING-1983-S350":
        "Bangladesh Merchant Shipping Ordinance, 1983 (Ord. XXVI of 1983), Section 350",
}

_APPLICABILITY = {
    "flag": "BD",
    "operation": "SEA_VOYAGE",
    "ship_type": None,          # filled from vessel at run time
    "zone_type": "TERRITORIAL",
    "coastal_state": "BD",
    "port": "CHITTAGONG",
}


_STATE_DB = None


def state_db():
    global _STATE_DB
    if _STATE_DB is None:
        _STATE_DB = load_state_participation()
    return _STATE_DB


def assess(ctx, *, company: dict, vessel: dict,
           applicability_facts: dict | None = None) -> ComplianceResult:
    rules = load_rules()
    app_facts = dict(_APPLICABILITY)
    app_facts["ship_type"] = vessel.get("ship_type", "CARGO")
    app_facts["gross_tonnage"] = vessel.get("gross_tonnage")
    # treaty position of the flag at the relevant date (Part 6.5 resolver)
    app_facts["annex_ratified_for_flag"] = state_db().ratified_annexes(
        vessel.get("flag", "BD"), ctx.eval_date)
    if applicability_facts:
        app_facts.update(applicability_facts)

    items = []
    law_versions: dict[str, str] = {}
    rule_versions: dict[str, str] = {}

    for rule_id, spec in rules.items():
        outcome = execute_rule(spec, ctx,
                               rule_version_id=f"{rule_id}-v{spec.rule_version}",
                               applicability_facts=app_facts)
        provision_id = spec.legal_source["provision_id"]
        law_versions[provision_id] = spec.legal_source.get("legal_version_id", "unversioned")
        rule_versions[rule_id] = f"v{spec.rule_version}"

        items.append(item_from_outcome(
            outcome,
            layer="L2_FLAG",
            requirement=spec.outcome.get("contract_requirement", spec.domain),
            why_applicable=(f"flag={app_facts['flag']}, ship_type={app_facts['ship_type']}, "
                            f"GT={app_facts.get('gross_tonnage')}, "
                            f"operation={app_facts['operation']} on {ctx.eval_date} "
                            f"matches applicability predicate"),
            source_law=_SOURCE_TITLES.get(provision_id, provision_id),
            amended=True,
            in_force_on_date=True,
            advisory=not spec.is_mandatory,
        ))

    return ComplianceResult(
        company_id=company["id"],
        entity_type="VESSEL",
        entity_id=vessel["id"],
        as_of_date=ctx.eval_date,
        items=items,
        law_versions_used=law_versions,
        rule_versions_used=rule_versions,
    )


def assess_vessel() -> ComplianceResult:
    """P1 exit-criteria assessment: MV PADMA STAR (seed module)."""
    ctx = seed.build_context()
    return assess(ctx, company=seed.COMPANY, vessel=seed.VESSEL,
                  applicability_facts=seed.APPLICABILITY_FACTS)


def assess_fleet() -> list[dict]:
    """Demo fleet — real engine over three vessels (RED / GREEN / YELLOW)."""
    from . import seed as padma

    out = []

    ctx = padma.build_context()
    out.append(_fleet_entry(padma.COMPANY, padma.VESSEL,
                            assess(ctx, company=padma.COMPANY, vessel=padma.VESSEL,
                                   applicability_facts=padma.APPLICABILITY_FACTS)))

    for entry in fleet.FLEET:
        if "seed_module" in entry:
            continue                      # padma handled above
        ctx = fleet.build_context(entry["vessel"], entry["crew"],
                                  entry["evidence"], entry["company"])
        out.append(_fleet_entry(entry["company"], entry["vessel"],
                                assess(ctx, company=entry["company"],
                                       vessel=entry["vessel"])))
    return out


def _fleet_entry(company: dict, vessel: dict, result: ComplianceResult) -> dict:
    counts = {s.value: 0 for s in Status}
    for item in result.items:
        counts[item.status.value] += 1
    return {
        "company": company["name"],
        "vessel_id": vessel["id"],
        "name": vessel["name"],
        "imo_number": vessel["imo_number"],
        "flag": vessel["flag"],
        "ship_type": vessel["ship_type"],
        "gross_tonnage": vessel["gross_tonnage"],
        "build_date": vessel["build_date"],
        "class_society": vessel["class_society"],
        "status": result.overall_status.value,
        "counts": counts,
        "lawyer_review_queue": [i.obligation_id for i in result.lawyer_review_queue],
        "as_of_date": result.as_of_date.isoformat(),
    }


def summary(result: ComplianceResult) -> str:
    lines = [
        f"MRIS vessel assessment — {seed.VESSEL['name']} (IMO {seed.VESSEL['imo_number']}), "
        f"flag {seed.VESSEL['flag']}, as of {result.as_of_date}",
        f"OVERALL: {result.overall_status.value}",
        "",
    ]
    for item in result.items:
        lines.append(f"  [{item.status.value:5}] {item.obligation_id}")
        lines.append(f"          {item.contract.requirement}")
        if item.status is not Status.GREEN:
            lines.append(f"          action: {item.contract.required_action}")
            lines.append(f"          consequence: {item.contract.consequence}")
        if item.contract.lawyer_review_needed:
            lines.append("          -> lawyer review required (48 h SLA)")
        lines.append("")
    if result.lawyer_review_queue:
        lines.append(f"Legal review queue: {[i.obligation_id for i in result.lawyer_review_queue]}")
    else:
        lines.append("Legal review queue: empty")
    lines.append(f"Law versions used: {result.law_versions_used}")
    lines.append(f"Rule versions used: {result.rule_versions_used}")
    return "\n".join(lines)


def demo_manifest_info() -> str:
    from ..corpus import load_manifest
    manifest = load_manifest()
    return (f"corpus manifest: {len(manifest['instruments'])} BD instruments, "
            f"{len(manifest['international_instruments'])} international instruments, "
            f"{len(manifest['open_items_register'])} open verification items")
