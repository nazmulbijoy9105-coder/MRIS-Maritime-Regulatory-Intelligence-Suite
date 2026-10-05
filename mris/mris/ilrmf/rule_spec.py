"""Rule specification: YAML surface (Part 9.2) -> validated JSONB AST.

A rule that fails parsing or type-checking can never reach ACTIVE
(Principle 12: AI may extract; only a human approves; the engine enforces
that nothing ill-typed or unparseable gets there).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from . import ast as A
from .parser import parse_expression
from .types import TypeChecker, TypeCheckError


class RuleSpecError(ValueError):
    pass


MANDATORY = "MANDATORY"
ADVISORY = "ADVISORY"

_STATUS_LADDER_KEYS = {"RED", "YELLOW", "BLACK", "GREEN"}


@dataclass
class RuleSpec:
    rule_id: str
    rule_version: int
    domain: str
    legal_source: dict                      # {provision_id, legal_version_id}
    applicability: dict
    condition: dict                         # {type, expression}
    outcome: dict
    evidence_required: list[str]
    status_ladder: dict[str, str]
    obligation_dimension: str | None = None  # for LCA-1 grouping (Part 9.6)
    ast: Any = None
    ast_json: dict = field(default_factory=dict)

    @property
    def condition_type(self) -> str:
        return self.condition.get("type", MANDATORY)

    @property
    def is_mandatory(self) -> bool:
        return self.condition_type != ADVISORY


REQUIRED_FIELDS = ("rule_id", "rule_version", "domain", "legal_source",
                   "applicability", "condition", "outcome", "evidence_required",
                   "status_ladder")


def parse_rule_spec(source: str | dict, schema: dict[str, str] | None = None) -> RuleSpec:
    data = yaml.safe_load(source) if isinstance(source, str) else dict(source)
    if not isinstance(data, dict):
        raise RuleSpecError("rule spec must be a mapping")

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise RuleSpecError(f"rule spec missing fields: {missing}")

    if not isinstance(data["legal_source"], dict) or "provision_id" not in data["legal_source"]:
        raise RuleSpecError("legal_source.provision_id is required (Principle 7)")

    cond = data["condition"]
    if not isinstance(cond, dict) or "expression" not in cond:
        raise RuleSpecError("condition.expression is required")
    if cond.get("type", MANDATORY) not in (MANDATORY, ADVISORY):
        raise RuleSpecError("condition.type must be MANDATORY or ADVISORY")

    ladder = data["status_ladder"]
    if not isinstance(ladder, dict) or not set(ladder) <= _STATUS_LADDER_KEYS:
        raise RuleSpecError(f"status_ladder keys must be within {_STATUS_LADDER_KEYS}")

    try:
        expr = parse_expression(str(cond["expression"]))
    except SyntaxError as exc:
        raise RuleSpecError(f"ILRMF-DSL parse error: {exc}") from exc

    try:
        TypeChecker(schema).check(expr)
    except TypeCheckError as exc:
        raise RuleSpecError(f"ILRMF-DSL type error: {exc}") from exc

    return RuleSpec(
        rule_id=str(data["rule_id"]),
        rule_version=int(data["rule_version"]),
        domain=str(data["domain"]),
        legal_source=dict(data["legal_source"]),
        applicability=dict(data["applicability"]),
        condition=dict(cond),
        outcome=dict(data["outcome"]),
        evidence_required=list(data["evidence_required"]),
        status_ladder=dict(ladder),
        obligation_dimension=data.get("obligation_dimension"),
        ast=expr,
        ast_json=A.to_json(expr),
    )


def definition_json(spec: RuleSpec) -> dict:
    """The JSONB payload stored in rule_version.definition."""
    return {
        "rule_id": spec.rule_id,
        "rule_version": spec.rule_version,
        "domain": spec.domain,
        "legal_source": spec.legal_source,
        "applicability": spec.applicability,
        "condition": {"type": spec.condition_type, "ast": spec.ast_json},
        "outcome": spec.outcome,
        "evidence_required": spec.evidence_required,
        "status_ladder": spec.status_ladder,
        "obligation_dimension": spec.obligation_dimension,
    }
