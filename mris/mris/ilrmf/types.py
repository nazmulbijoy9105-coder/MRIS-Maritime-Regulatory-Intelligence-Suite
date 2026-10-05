"""Typed domains + static type checker for ILRMF-DSL (Part 9.3).

Every rule is type-checked at approval time: a rule that type-errors can
never reach ACTIVE. Paths resolve to ANY absent a schema hint; literals and
builtin signatures are always checked.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .ast import (Binary, Expr, FuncCall, Literal, Path, Quantifier, Unary,
                  UnknownLit)

# --- typed domains ----------------------------------------------------------
BOOL = "BOOL"
NUMBER = "NUMBER"
STRING = "STRING"
DATE = "DATE"
DURATION = "DURATION"
RANK = "RANK"
CERT_TYPE = "CERT_TYPE"
EVIDENCE = "EVIDENCE"
ANY = "ANY"

NUMERIC = {NUMBER, DURATION}
COMPARABLE = {NUMBER, DURATION, DATE, STRING, RANK, CERT_TYPE}


class TypeCheckError(TypeError):
    pass


def set_of(t: str) -> str:
    return f"SET<{t}>"


def elem_type(t: str) -> str:
    return t[4:-1] if t.startswith("SET<") and t.endswith(">") else ANY


@dataclass(frozen=True)
class Signature:
    params: tuple          # (name, type) — positional
    kwargs: tuple          # (name, type) — named (e.g. at:)
    returns: str


def _sig(*params: str, returns: str = BOOL, **kwargs: str) -> Signature:
    return Signature(tuple(params), tuple(kwargs.items()), returns)


# builtin signatures — mirrors Part 9.3 built-in list
BUILTIN_SIGNATURES: dict[str, Signature] = {
    # temporal
    "in_force":        _sig(STRING, returns=BOOL, at=DATE),
    "version_at":      _sig(STRING, returns=STRING, at=DATE),
    "days_until":      _sig(DATE, returns=DURATION),
    "expired":         _sig(EVIDENCE, returns=BOOL, at=DATE),
    "expires_within":  _sig(EVIDENCE, NUMBER, returns=BOOL),
    # evidence
    "exists":          _sig(STRING, ANY, returns=BOOL),
    "verified":        _sig(EVIDENCE, returns=BOOL),
    "issuer_matches":  _sig(EVIDENCE, STRING, returns=BOOL),
    # certificates
    "cert_valid":             _sig(STRING, ANY, returns=BOOL, at=DATE),
    "cert_imo_harmonized":    _sig(CERT_TYPE, returns=BOOL),
    # crew
    "coc_valid":              _sig(ANY, returns=BOOL, at=DATE),
    "rest_hours_compliant":   _sig(ANY, NUMBER, returns=BOOL),
    # voyage / zone
    "zone_at":         _sig(NUMBER, NUMBER, returns=STRING, at=DATE),
    "leg_segments":    _sig(ANY, returns=set_of(ANY)),
    "annex_ratified":  _sig(STRING, STRING, returns=BOOL, at=DATE),
    # arithmetic / date
    "age_of":          _sig(ANY, returns=NUMBER, at=DATE),
    "gt":              _sig(ANY, returns=NUMBER),
    "keel_laid_before": _sig(ANY, DATE, returns=BOOL),
    # jurisdiction
    "layer_applies":   _sig(STRING, ANY, returns=BOOL),
    "precedence_max":  _sig(set_of(NUMBER), returns=NUMBER),
}


class TypeChecker:
    """Structural type check. `schema` maps root identifier -> type (optional)."""

    def __init__(self, schema: Optional[dict[str, str]] = None):
        self.schema = schema or {}

    # entry ---------------------------------------------------------------
    def check(self, expr: Expr) -> str:
        return self._check(expr, bound={})

    def _check(self, expr: Expr, bound: dict[str, str]) -> str:
        if isinstance(expr, Literal):
            return expr.type
        if isinstance(expr, UnknownLit):
            return ANY
        if isinstance(expr, Path):
            root = expr.parts[0]
            if isinstance(root, Expr):
                return ANY
            return bound.get(root, self.schema.get(root, ANY))
        if isinstance(expr, Unary):
            t = self._check(expr.operand, bound)
            if expr.op == "NOT" and t not in (BOOL, ANY):
                raise TypeCheckError(f"NOT applied to {t}, expected BOOL")
            return BOOL
        if isinstance(expr, Binary):
            return self._check_binary(expr, bound)
        if isinstance(expr, FuncCall):
            return self._check_call(expr, bound)
        if isinstance(expr, Quantifier):
            src_t = self.schema.get(expr.source, set_of(ANY))
            body_t = self._check(expr.body, {**bound, expr.var: elem_type(src_t)})
            if body_t not in (BOOL, ANY):
                raise TypeCheckError(
                    f"quantifier body must be BOOL, got {body_t}")
            return BOOL
        raise TypeCheckError(f"unknown expression {expr!r}")

    def _check_binary(self, expr: Binary, bound) -> str:
        lt = self._check(expr.left, bound)
        rt = self._check(expr.right, bound)
        op = expr.op
        if op in ("AND", "OR"):
            for t in (lt, rt):
                if t not in (BOOL, ANY):
                    raise TypeCheckError(f"{op} requires BOOL operands, got {t}")
            return BOOL
        if op in ("=", "!="):
            return BOOL
        if op in ("<", "<=", ">", ">="):
            for t in (lt, rt):
                if t not in COMPARABLE and t != ANY:
                    raise TypeCheckError(f"{op} not defined on {t}")
            return BOOL
        if op == "IN":
            return BOOL
        if op == "MATCHES":
            if lt not in (STRING, ANY) or rt not in (STRING, ANY):
                raise TypeCheckError("MATCHES requires STRING operands")
            return BOOL
        if op in ("+", "-", "*", "/", "%"):
            for t in (lt, rt):
                if t not in NUMERIC and t != ANY:
                    raise TypeCheckError(f"arithmetic {op} not defined on {t}")
            return NUMBER
        raise TypeCheckError(f"unknown operator {op}")

    def _check_call(self, expr: FuncCall, bound) -> str:
        sig = BUILTIN_SIGNATURES.get(expr.name)
        if sig is None:
            raise TypeCheckError(f"unknown function {expr.name!r}")
        n_args = len(expr.args) + (1 if expr.receiver else 0)
        if n_args != len(sig.params):
            raise TypeCheckError(
                f"{expr.name} expects {len(sig.params)} positional args, got {n_args}")
        for (kname, _), supplied in zip(sig.kwargs, [k for k, _ in expr.kwargs]):
            if kname != supplied:
                raise TypeCheckError(
                    f"{expr.name} expects named arg {kname!r}, got {supplied!r}")
        return sig.returns
