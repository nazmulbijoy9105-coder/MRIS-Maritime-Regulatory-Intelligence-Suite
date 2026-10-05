"""Compliance engine tests: precedence, STRICTER/CONFLICT, LCA-1, result contract."""
from __future__ import annotations

from datetime import date

from mris.engine import (ComplianceResult, Constraint, Layer, Obligation, Status,
                         combine_obligations, execute_rule, item_from_outcome,
                         match_applicability, provision_in_force, resolve_voyage,
                         select_version, stricter, worst)
from mris.engine.lca1 import Leg, RuleCandidate, Segment
from mris.ilrmf import EvalContext, Tri, parse_rule_spec

TODAY = date(2026, 10, 6)


def ob(dimension, layer, constraint=None, status=Status.GREEN, rule="R1", **kw):
    return Obligation(dimension=dimension, layer=layer,
                      provision_ids=[f"{rule}-P"], rule_id=rule,
                      rule_version_id=f"{rule}-v1", legal_version_id="LV1",
                      requirement=kw.get("requirement", f"{rule} requirement"),
                      constraint=constraint, status=status)


# ---------------------------------------------------------------------------
# status ordering
# ---------------------------------------------------------------------------

def test_status_ordering_and_worst():
    assert Status.GREEN < Status.YELLOW < Status.RED < Status.BLACK
    assert worst([Status.GREEN, Status.RED, Status.YELLOW]) is Status.RED
    assert worst([]) is Status.BLACK        # no data => fail closed


# ---------------------------------------------------------------------------
# STRICTER / CONFLICT
# ---------------------------------------------------------------------------

def test_stricter_min_max():
    assert stricter(Constraint.min(5), Constraint.min(8)) == Constraint.min(8)
    assert stricter(Constraint.max(10), Constraint.max(6)) == Constraint.max(6)
    assert stricter(Constraint.min(8), Constraint.max(7)) is None     # CONFLICT
    assert stricter(Constraint.min(6), Constraint.max(8)) == Constraint.min(6)


def test_stricter_sets():
    merged = stricter(Constraint.one_of("A", "B", "C"), Constraint.one_of("B", "C", "D"))
    assert merged == Constraint("SET", frozenset({"B", "C"}))
    assert stricter(Constraint.one_of("A"), Constraint.one_of("B")) is None


def test_combine_stricter_manning():
    """L1 requires 5 crew, flag law requires 8 => merged MIN(8), binding."""
    obs = [
        ob("manning_level", Layer.L1_INTL, Constraint.min(5), rule="IMO-R1"),
        ob("manning_level", Layer.L2_FLAG, Constraint.min(8), rule="BD-R1"),
    ]
    combined = combine_obligations(obs)
    dim = combined.dimensions["manning_level"]
    assert dim.constraint == Constraint.min(8)
    assert dim.conflict is None
    assert combined.status is Status.GREEN


def test_combine_conflict_is_black():
    obs = [
        ob("discharge_standard", Layer.L1_INTL, Constraint.max(15), rule="IMO-R2"),
        ob("discharge_standard", Layer.L4_PORT, Constraint.min(25), rule="PORT-R2"),
    ]
    combined = combine_obligations(obs)
    dim = combined.dimensions["discharge_standard"]
    assert dim.conflict is not None
    assert dim.status is Status.BLACK
    assert combined.status is Status.BLACK
    assert set(dim.conflict.provision_ids) == {"IMO-R2-P", "PORT-R2-P"}


def test_advisory_cannot_lower_statutory_green():
    """Principle 15 invariant."""
    obs = [
        ob("manning_level", Layer.L2_FLAG, status=Status.GREEN, rule="BD-R1"),
        ob("manning_level", Layer.L6_CONTRACT, status=Status.YELLOW, rule="SIRE-R1"),
    ]
    combined = combine_obligations(obs)
    assert combined.status is Status.GREEN          # binding dominates
    assert [o.rule_id for o in combined.advisory_items] == ["SIRE-R1"]

    # but a binding RED always dominates everything
    obs2 = obs + [ob("sewage", Layer.L2_FLAG, status=Status.RED, rule="BD-R2")]
    assert combine_obligations(obs2).status is Status.RED


# ---------------------------------------------------------------------------
# applicability
# ---------------------------------------------------------------------------

def test_applicability_three_valued():
    facts = {"flag": "BD", "ship_type": "CARGO"}
    assert match_applicability({"all": [{"flag": ["BD"]}]}, facts) is Tri.TRUE
    assert match_applicability({"all": [{"flag": ["PA"]}]}, facts) is Tri.FALSE
    assert match_applicability({"all": [{"gt_band": ["A"]}]}, facts) is Tri.UNKNOWN
    assert match_applicability(
        {"all": [{"flag": ["BD"]}], "any": [{"ship_type": ["TANKER"]}, {"ship_type": ["CARGO"]}]},
        facts) is Tri.TRUE


# ---------------------------------------------------------------------------
# rule execution + fail-closed
# ---------------------------------------------------------------------------

RULE_YAML = {
    "rule_id": "T-S082-R001", "rule_version": 1, "domain": "MANNING",
    "legal_source": {"provision_id": "T-S082", "legal_version_id": "LV1"},
    "applicability": {"all": [{"flag": ["BD"]}]},
    "condition": {"type": "MANDATORY",
                  "expression": 'EXISTS e IN evidence : e.evidence_type = "SMD"'},
    "outcome": {"compliant_if": "true"},
    "evidence_required": ["SMD"],
    "status_ladder": {},
}


def test_mandatory_unknown_is_black():
    spec = parse_rule_spec(RULE_YAML)
    # applicability fact missing => BLACK
    outcome = execute_rule(spec, EvalContext(eval_date=TODAY), applicability_facts={})
    assert outcome.status is Status.BLACK
    assert outcome.lawyer_review_needed

    # evidence absent => definite FALSE => RED
    outcome = execute_rule(spec, EvalContext(eval_date=TODAY),
                           applicability_facts={"flag": "BD"})
    assert outcome.status is Status.RED

    # evidence present => GREEN
    c = EvalContext(eval_date=TODAY, evidence=[{"evidence_type": "SMD"}])
    outcome = execute_rule(spec, c, applicability_facts={"flag": "BD"})
    assert outcome.status is Status.GREEN


def test_advisory_rule_never_red():
    spec = parse_rule_spec({**RULE_YAML, "rule_id": "T-ADV-R001",
                            "condition": {"type": "ADVISORY", "expression": "FALSE"}})
    outcome = execute_rule(spec, EvalContext(eval_date=TODAY),
                           applicability_facts={"flag": "BD"})
    assert outcome.status is Status.YELLOW          # never RED/BLACK


def test_not_applicable_is_green_with_reason():
    spec = parse_rule_spec(RULE_YAML)
    outcome = execute_rule(spec, EvalContext(eval_date=TODAY),
                           applicability_facts={"flag": "PA"})
    assert outcome.status is Status.GREEN
    assert "not applicable" in outcome.reason


# ---------------------------------------------------------------------------
# LCA-1
# ---------------------------------------------------------------------------

def _cand(rule, layer, dim, jurisdiction=None, constraint=None, applicability=None):
    return RuleCandidate(
        rule_id=rule, layer=layer, dimension=dim, requirement=f"{rule} req",
        provision_ids=[f"{rule}-P"], rule_version_id=f"{rule}-v1",
        legal_version_id="LV1", jurisdiction_id=jurisdiction,
        applicability=applicability or {}, constraint=constraint)


def test_lca1_voyage_resolution_stricter_and_conflict():
    legs = [
        Leg(seq=1, zone_type="TERRITORIAL", coastal_state="BD", port="CHITTAGONG",
            segments=[Segment(Layer.L1_INTL, "INTL", TODAY),
                      Segment(Layer.L2_FLAG, "BD", TODAY),
                      Segment(Layer.L3_COASTAL, "BD", TODAY),
                      Segment(Layer.L4_PORT, "CHITTAGONG", TODAY),
                      Segment(Layer.L6_CONTRACT, "CONTRACT", TODAY)]),
    ]
    candidates = [
        _cand("IMO-MANNING", Layer.L1_INTL, "manning_level", constraint=Constraint.min(5)),
        _cand("BD-MANNING", Layer.L2_FLAG, "manning_level", jurisdiction="BD", constraint=Constraint.min(8)),
        _cand("PORT-DISCHARGE", Layer.L4_PORT, "discharge_standard", jurisdiction="CHITTAGONG",
              constraint=Constraint.min(25), applicability={"psc_entry_only": True}),
        _cand("IMO-DISCHARGE", Layer.L1_INTL, "discharge_standard", constraint=Constraint.max(15)),
        _cand("PORT-DISCHARGE-STD", Layer.L4_PORT, "discharge_standard", jurisdiction="CHITTAGONG",
              constraint=Constraint.min(25), applicability={"psc_entry_only": True}),
        _cand("SIRE-REST", Layer.L6_CONTRACT, "rest_hours"),
    ]
    result = resolve_voyage(legs, candidates, vessel_flag="BD", domestic=True, as_of=TODAY)

    leg = result.legs[0]
    assert leg.combined.dimensions["manning_level"].constraint == Constraint.min(8)
    assert leg.combined.dimensions["discharge_standard"].conflict is not None
    assert result.overall_status is Status.BLACK
    assert result.conflict_items[0]["sla_hours"] == 48
    assert result.conflict_items[0]["left"]["layer"] in ("L1", "L4")


def test_lca1_psc_asymmetry_foreign_flag():
    """Foreign-flag vessel at a port: L4 non-entry rules are not binding law."""
    legs = [Leg(seq=1, zone_type="TERRITORIAL", coastal_state="SG", port="SINGAPORE",
                segments=[Segment(Layer.L4_PORT, "SINGAPORE", TODAY)])]
    candidates = [
        _cand("PORT-FULL", Layer.L4_PORT, "berth_rules",
              applicability={"psc_entry_only": False}),
        _cand("PORT-ENTRY", Layer.L4_PORT, "port_entry",
              applicability={"psc_entry_only": True}),
    ]
    foreign = resolve_voyage(legs, candidates, vessel_flag="BD", domestic=False, as_of=TODAY)
    dims = foreign.legs[0].combined.dimensions
    assert "berth_rules" not in dims          # filtered out for foreign flag
    assert "port_entry" in dims

    domestic = resolve_voyage(legs, candidates, vessel_flag="SG", domestic=True, as_of=TODAY)
    assert "berth_rules" in domestic.legs[0].combined.dimensions


def test_lca1_applicability_unknown_is_black():
    legs = [Leg(seq=1, zone_type="EEZ", coastal_state="BD")]
    candidates = [_cand("BD-EEZ", Layer.L3_COASTAL, "eez_rule", jurisdiction="BD",
                        applicability={"cargo_class": ["DG"]})]
    result = resolve_voyage(legs, candidates, vessel_flag="BD", as_of=TODAY)
    assert result.overall_status is Status.BLACK


def test_lca1_aggregates_worst_across_legs():
    legs = [
        Leg(seq=1, zone_type="TERRITORIAL", coastal_state="BD"),
        Leg(seq=2, zone_type="HIGH_SEAS", coastal_state=None),
    ]
    candidates = [
        _cand("BD-COASTAL", Layer.L3_COASTAL, "pollution", jurisdiction="BD"),
        _cand("IMO-HIGHSEAS", Layer.L1_INTL, "dg_rules",
              applicability={"zone_type": ["HIGH_SEAS"], "cargo_class": ["DG"]}),
    ]
    result = resolve_voyage(legs, candidates, vessel_flag="BD", as_of=TODAY)
    assert result.legs[0].status is Status.GREEN
    assert result.legs[1].status is Status.BLACK
    assert result.overall_status is Status.BLACK       # worst across legs
    assert result.drill_down["1"]["status"] == "GREEN"
    assert result.drill_down["2"]["status"] == "BLACK"


# ---------------------------------------------------------------------------
# compliance result contract
# ---------------------------------------------------------------------------

def test_result_contract_and_principle15():
    spec = parse_rule_spec(RULE_YAML)
    c = EvalContext(eval_date=TODAY, evidence=[{"evidence_type": "SMD"}])
    outcome = execute_rule(spec, c, applicability_facts={"flag": "BD"})
    item = item_from_outcome(outcome, layer="L2_FLAG", requirement="manning doc",
                             why_applicable="flag=BD", source_law="MSO 1983 s.82",
                             amended=True, in_force_on_date=True)
    result = ComplianceResult(company_id="co1", entity_type="VESSEL",
                              entity_id="v1", as_of_date=TODAY, items=[item])
    d = result.as_dict()
    assert d["overall_status"] == "GREEN"
    for key in ("requirement", "why_applicable", "source_law", "provision",
                "legal_version", "amended", "in_force_on_date", "evidence",
                "rule_executed", "facts_used", "result", "missing",
                "required_action", "deadline", "consequence", "lawyer_review_needed"):
        assert key in d["items"][0], key

    # advisory-only result cannot lower GREEN (Principle 15)
    adv = item_from_outcome(outcome, layer="L6_CONTRACT", requirement="SIRE",
                            why_applicable="charter party", source_law="contract",
                            amended=None, in_force_on_date=True, advisory=True)
    result2 = ComplianceResult(company_id="co1", entity_type="VESSEL", entity_id="v1",
                               as_of_date=TODAY, items=[item, adv])
    assert result2.overall_status is Status.GREEN
    assert len(result2.advisory_items) == 1


# ---------------------------------------------------------------------------
# temporal (Principle 10)
# ---------------------------------------------------------------------------

def test_version_selection_time_travel():
    versions = [
        {"id": "v1", "effective_from": date(2020, 1, 1), "effective_to": date(2023, 1, 1)},
        {"id": "v2", "effective_from": date(2023, 1, 1), "effective_to": None},
    ]
    assert select_version(versions, date(2021, 6, 1))["id"] == "v1"
    assert select_version(versions, date(2024, 6, 1))["id"] == "v2"
    assert select_version(versions, date(2019, 6, 1)) is None      # future law never early

    validity = [{"valid_from": date(2020, 1, 1), "valid_to": date(2023, 1, 1)},
                {"valid_from": date(2023, 1, 1), "valid_to": None}]
    assert provision_in_force(validity, date(2021, 1, 1)) is True
    assert provision_in_force(validity, date(2030, 1, 1)) is True
    assert provision_in_force(validity, date(2010, 1, 1)) is False
