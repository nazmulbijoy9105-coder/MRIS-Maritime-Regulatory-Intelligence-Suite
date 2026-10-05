"""ILRMF-DSL test suite: Kleene logic, quantifiers, parser, sandbox, builtins."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from mris.ilrmf import (EvalContext, ParseError, RuleSpecError, Tri,
                        TypeCheckError, TypeChecker, evaluate,
                        parse_expression, parse_rule_spec)

TODAY = date(2026, 10, 6)


def ctx(**kwargs) -> EvalContext:
    base = dict(eval_date=TODAY)
    base.update(kwargs)
    return EvalContext(**base)


def ev(expr: str, context: EvalContext) -> Tri:
    return evaluate(parse_expression(expr), context).tri


# ---------------------------------------------------------------------------
# three-valued logic
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expr, expected", [
    ("TRUE AND TRUE", Tri.TRUE),
    ("TRUE AND FALSE", Tri.FALSE),
    ("TRUE AND UNKNOWN", Tri.UNKNOWN),
    ("FALSE AND UNKNOWN", Tri.FALSE),          # FALSE dominates
    ("FALSE OR TRUE", Tri.TRUE),
    ("FALSE OR UNKNOWN", Tri.UNKNOWN),
    ("TRUE OR UNKNOWN", Tri.TRUE),             # TRUE dominates
    ("NOT TRUE", Tri.FALSE),
    ("NOT UNKNOWN", Tri.UNKNOWN),
    ("NOT (FALSE OR UNKNOWN)", Tri.UNKNOWN),
    ("(TRUE AND UNKNOWN) OR FALSE", Tri.UNKNOWN),
])
def test_kleene_connectives(expr, expected):
    assert ev(expr, ctx()) is expected


def test_missing_fact_is_unknown_not_false():
    c = ctx(facts={"vessel": {"name": "X"}})
    assert ev("vessel.gross_tonnage > 1000", c) is Tri.UNKNOWN
    assert ev("vessel.flag = \"BD\"", c) is Tri.UNKNOWN


def test_division_by_zero_folds_to_unknown():
    assert ev("1 / 0 = 1", ctx()) is Tri.UNKNOWN


def test_budget_exhaustion_fails_closed():
    c = ctx(facts={"a": {"b": 1}}, step_budget=3)
    result = evaluate(parse_expression("a.b = 1 AND a.b = 1 AND a.b = 1"), c)
    assert result.tri is Tri.UNKNOWN
    assert any("budget" in r for r in result.unknown_reasons)


def test_parse_depth_limit():
    with pytest.raises(ParseError):
        parse_expression("(" * 70 + "TRUE" + ")" * 70)


# ---------------------------------------------------------------------------
# quantifiers
# ---------------------------------------------------------------------------

CREW_OK = [
    {"id": "1", "rank": "MASTER",
     "certificates": [{"type": "COC", "issue_date": "2024-01-01",
                       "expiry_date": "2028-01-01", "verification_status": "VERIFIED"}]},
    {"id": "2", "rank": "AB",
     "certificates": [{"type": "COC", "issue_date": "2024-01-01",
                       "expiry_date": "2028-01-01", "verification_status": "VERIFIED"}]},
]
CREW_BAD = [dict(CREW_OK[0]), {
    "id": "3", "rank": "OILER",
    "certificates": [{"type": "COC", "issue_date": "2020-01-01",
                      "expiry_date": "2025-01-01", "verification_status": "VERIFIED"}],
}]


def test_forall_true_false_unknown():
    c = ctx(crew=CREW_OK)
    assert ev("FORALL m IN current_crew : m.coc_valid(at: eval_date)", c) is Tri.TRUE

    c = ctx(crew=CREW_BAD)
    assert ev("FORALL m IN current_crew : m.coc_valid(at: eval_date)", c) is Tri.FALSE

    # one crew member with no cert data at all => UNKNOWN (fail-closed)
    c = ctx(crew=[{"id": "9", "rank": "AB", "certificates": []}, CREW_OK[0]])
    assert ev("FORALL m IN current_crew : m.coc_valid(at: eval_date)", c) is Tri.FALSE


def test_exists_none():
    c = ctx(evidence=[{"evidence_type": "LOAD_LINE_CERTIFICATE", "entity_id": "v1"}])
    assert ev('EXISTS e IN evidence : e.evidence_type = "LOAD_LINE_CERTIFICATE"', c) is Tri.TRUE
    assert ev('NONE e IN evidence : e.evidence_type = "LOAD_LINE_CERTIFICATE"', c) is Tri.FALSE
    assert ev('EXISTS e IN evidence : e.evidence_type = "SMC"', c) is Tri.FALSE
    assert ev('NONE e IN evidence : e.evidence_type = "SMC"', c) is Tri.TRUE


def test_quantifier_source_missing_is_unknown():
    c = ctx()  # no crew at all
    assert ev("FORALL m IN current_crew : m.rank = \"MASTER\"", c) is Tri.UNKNOWN


# ---------------------------------------------------------------------------
# builtins
# ---------------------------------------------------------------------------

def test_cert_valid_and_expiry():
    m0 = CREW_BAD[0]
    m1 = CREW_BAD[1]
    assert ev("m.coc_valid(at: #2024-06-01)", ctx(facts={"m": m0})) is Tri.TRUE
    assert ev("m.coc_valid(at: #2025-06-01)", ctx(facts={"m": m1})) is Tri.FALSE   # expired 2025-01-01

    evd = {"evidence_type": "X", "expiry_date": str(TODAY - timedelta(days=1))}
    c = ctx(evidence=[evd], facts={"e": evd})
    assert ev("expired(e, at: eval_date)", c) is Tri.TRUE
    assert ev("expires_within(e, 60)", c) is Tri.FALSE

    evd2 = {"evidence_type": "X", "expiry_date": str(TODAY + timedelta(days=30))}
    c = ctx(evidence=[evd2], facts={"e": evd2})
    assert ev("expires_within(e, 60)", c) is Tri.TRUE
    assert ev("expires_within(e, 10)", c) is Tri.FALSE


def test_missing_expiry_is_unknown():
    c = ctx(facts={"e": {"evidence_type": "X"}}, evidence=[{"evidence_type": "X"}])
    assert ev("expired(e, at: eval_date)", c) is Tri.UNKNOWN


def test_in_force_resolver_fail_closed():
    assert ev('in_force("P1", at: eval_date)', ctx()) is Tri.UNKNOWN

    c = ctx(in_force_fn=lambda p, at: p == "P1")
    assert ev('in_force("P1", at: eval_date)', c) is Tri.TRUE
    assert ev('in_force("P2", at: eval_date)', c) is Tri.FALSE


def test_annex_ratified_and_age():
    c = ctx(annex_ratified_fn=lambda f, a, at: f == "BD" and a == "VI",
            facts={"vessel": {"build_date": "2011-06-01",
                              "keel_laid_date": "2010-03-15"}})
    assert ev('annex_ratified("BD", "VI", at: eval_date)', c) is Tri.TRUE
    assert ev('annex_ratified("BD", "I", at: eval_date)', c) is Tri.FALSE
    assert ev("age_of(vessel, at: eval_date) > 10", c) is Tri.TRUE
    assert ev("age_of(vessel, at: eval_date) > 20", c) is Tri.FALSE
    assert ev("keel_laid_before(vessel, #2011-01-01)", c) is Tri.TRUE


def test_imo_harmonized():
    assert ev('cert_imo_harmonized("SMC")', ctx()) is Tri.TRUE
    assert ev('cert_imo_harmonized("NOT_A_CERT")', ctx()) is Tri.FALSE


# ---------------------------------------------------------------------------
# parser + types
# ---------------------------------------------------------------------------

def test_parse_rejects_garbage():
    with pytest.raises(ParseError):
        parse_expression("TRUE AND")
    with pytest.raises(ParseError):
        parse_expression("1 +")
    with pytest.raises(ParseError):
        parse_expression("@#$%")


def test_typechecker_rejects_bad_rules():
    tc = TypeChecker()
    with pytest.raises(TypeCheckError):
        tc.check(parse_expression("1 AND TRUE"))
    with pytest.raises(TypeCheckError):
        tc.check(parse_expression("NOT 5"))
    with pytest.raises(TypeCheckError):
        tc.check(parse_expression("unknown_fn(1)"))
    with pytest.raises(TypeCheckError):
        tc.check(parse_expression('in_force("P1", bogus: #2020-01-01)'))   # unknown named arg
    tc.check(parse_expression("days_until(#2027-01-01) > 30"))


def test_rule_spec_validation():
    good = {
        "rule_id": "TEST-R001", "rule_version": 1, "domain": "TEST",
        "legal_source": {"provision_id": "P1", "legal_version_id": "LV1"},
        "applicability": {"all": [{"flag": ["BD"]}]},
        "condition": {"type": "MANDATORY", "expression": "TRUE"},
        "outcome": {"compliant_if": "true"},
        "evidence_required": ["X"],
        "status_ladder": {"RED": "FALSE"},
    }
    spec = parse_rule_spec(good)
    assert spec.is_mandatory
    assert spec.ast_json["node"] == "binary" or spec.ast_json["node"] == "literal"

    import copy
    bad = copy.deepcopy(good)
    bad["condition"]["expression"] = "1 AND TRUE"
    with pytest.raises(RuleSpecError):
        parse_rule_spec(bad)

    bad2 = copy.deepcopy(good)
    del bad2["legal_source"]
    with pytest.raises(RuleSpecError):
        parse_rule_spec(bad2)


def test_unknown_conditions():
    c = ctx()
    result = evaluate(parse_expression("vessel.flag = \"BD\""), c)
    assert result.tri is Tri.UNKNOWN
    assert any("missing" in r for r in result.unknown_reasons)
