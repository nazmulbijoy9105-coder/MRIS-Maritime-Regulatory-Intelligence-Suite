"""Rule execution: applicability -> condition -> status ladder (Parts 9.2, 9.4).

Fail-closed mapping (Principle 11):
    MANDATORY rule: condition TRUE -> GREEN, FALSE -> RED, UNKNOWN -> BLACK
    ADVISORY  rule: TRUE -> GREEN, FALSE/UNKNOWN -> YELLOW (never RED/BLACK)
Applicability uncertain (missing dimension facts) => BLACK, never a guess.

status_ladder entries may be ILRMF-DSL expressions, evaluated in severity
order BLACK > RED > YELLOW; first TRUE wins. Non-parseable entries are kept
as documentation and the default mapping applies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .status import Status
from ..ilrmf import EvalContext, RuleSpec, Tri, evaluate, parse_expression

_LADDER_ORDER = [Status.BLACK, Status.RED, Status.YELLOW]


# ---------------------------------------------------------------------------
# Applicability predicate (Part 9.4 dimensions)
# ---------------------------------------------------------------------------

def _leaf_matches(dimension: str, expected, facts: dict) -> Tri:
    # numeric vessel dimensions (Part 9.4): gt_min / gt_max compare gross tonnage
    if dimension in ("gt_min", "gt_max"):
        actual = facts.get("gross_tonnage")
        if actual is None:
            return Tri.UNKNOWN
        return Tri.of(float(actual) >= float(expected) if dimension == "gt_min"
                      else float(actual) <= float(expected))
    # treaty-position dimension: which MARPOL annexes the flag is bound by
    if dimension == "annex_ratified_for_flag":
        ratified = facts.get("annex_ratified_for_flag")
        if ratified is None:
            return Tri.UNKNOWN
        wanted = expected if isinstance(expected, (list, tuple, set)) else [expected]
        return Tri.of(any(a in ratified for a in wanted))
    actual = facts.get(dimension)
    if actual is None:
        return Tri.UNKNOWN
    if isinstance(expected, (list, tuple, frozenset, set)):
        return Tri.of(actual in expected)
    return Tri.of(actual == expected)


def match_applicability(applicability: dict, facts: dict) -> Tri:
    """all:/any: groups over leaf predicates; missing facts => UNKNOWN."""
    if not applicability:
        return Tri.TRUE

    results: list[Tri] = []
    for key, value in applicability.items():
        if key == "all":
            acc = Tri.TRUE
            for v in value:
                acc = acc.AND(_match_group(v, facts))
            results.append(acc)
        elif key == "any":
            acc = Tri.FALSE
            for v in value:
                acc = acc.OR(_match_group(v, facts))
            results.append(acc)
        else:
            results.append(_leaf_matches(key, value, facts))

    acc = Tri.TRUE
    for r in results:
        acc = acc.AND(r)
    return acc


def _match_group(group: dict, facts: dict) -> Tri:
    acc = Tri.TRUE
    for key, value in group.items():
        acc = acc.AND(_leaf_matches(key, value, facts))
    return acc


# ---------------------------------------------------------------------------
# Rule outcome
# ---------------------------------------------------------------------------

@dataclass
class RuleOutcome:
    rule_id: str
    rule_version_id: str
    provision_id: str
    legal_version_id: str
    status: Status
    applicable: Tri
    condition: Tri
    reason: str
    facts_used: dict = field(default_factory=dict)
    unknown_reasons: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    required_action: str | None = None

    @property
    def lawyer_review_needed(self) -> bool:
        return self.status is Status.BLACK


def _tri_to_status(tri: Tri, mandatory: bool) -> Status:
    if tri is Tri.TRUE:
        return Status.GREEN
    if not mandatory:
        return Status.YELLOW          # advisory never RED/BLACK
    return Status.RED if tri is Tri.FALSE else Status.BLACK


def _ladder_status(spec: RuleSpec, ctx: EvalContext, cond: Tri) -> Status | None:
    for status in _LADDER_ORDER:
        entry = spec.status_ladder.get(status.value)
        if not entry:
            continue
        try:
            expr = parse_expression(str(entry))
        except SyntaxError:
            continue                  # prose annotation; default mapping applies
        result = evaluate(expr, ctx)
        if result.tri is Tri.TRUE:
            return status
    return None


def execute_rule(spec: RuleSpec, ctx: EvalContext,
                 rule_version_id: str = "rv-1",
                 applicability_facts: dict | None = None) -> RuleOutcome:
    facts = applicability_facts if applicability_facts is not None else ctx.facts
    provision_id = spec.legal_source["provision_id"]
    legal_version_id = spec.legal_source.get("legal_version_id", "unversioned")

    applicable = match_applicability(spec.applicability, facts)
    if applicable is Tri.FALSE:
        return RuleOutcome(
            rule_id=spec.rule_id, rule_version_id=rule_version_id,
            provision_id=provision_id, legal_version_id=legal_version_id,
            status=Status.GREEN, applicable=applicable, condition=Tri.TRUE,
            reason=f"{spec.rule_id}: not applicable to this entity/date "
                   f"(applicability predicate false)",
            facts_used=facts, evidence_required=spec.evidence_required,
        )
    if applicable is Tri.UNKNOWN:
        return RuleOutcome(
            rule_id=spec.rule_id, rule_version_id=rule_version_id,
            provision_id=provision_id, legal_version_id=legal_version_id,
            status=Status.BLACK, applicable=applicable, condition=Tri.UNKNOWN,
            reason=f"{spec.rule_id}: applicability uncertain — missing dimension "
                   f"facts; fail-closed to BLACK (Principle 11)",
            facts_used=facts, evidence_required=spec.evidence_required,
        )

    result = evaluate(spec.ast, ctx)
    status = _ladder_status(spec, ctx, result.tri) or \
        _tri_to_status(result.tri, spec.is_mandatory)

    reason = (
        f"{spec.rule_id} [{spec.condition_type}] over {provision_id} "
        f"@ {ctx.eval_date}: condition={result.tri.value} => {status.value}"
    )
    if result.unknown_reasons:
        reason += " | unknowns: " + "; ".join(result.unknown_reasons[:5])

    return RuleOutcome(
        rule_id=spec.rule_id, rule_version_id=rule_version_id,
        provision_id=provision_id, legal_version_id=legal_version_id,
        status=status, applicable=applicable, condition=result.tri,
        reason=reason, facts_used=facts,
        unknown_reasons=result.unknown_reasons,
        evidence_required=spec.evidence_required,
    )
