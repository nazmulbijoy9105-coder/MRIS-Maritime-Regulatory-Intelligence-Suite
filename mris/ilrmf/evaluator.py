"""ILRMF-DSL sandboxed evaluator.

Guarantees (Part 9.3):
  * total — every expression yields TRUE/FALSE/UNKNOWN on every input
    (missing data, division by zero, budget exhaustion all fold to UNKNOWN);
  * sandboxed — no I/O, no unbounded recursion (depth cap), step budget;
  * deterministic — same (expression, facts) => same result;
  * fail-closed — UNKNOWN in a MANDATORY rule maps to BLACK at rule level.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .ast import (Binary, Expr, FuncCall, Literal, Path, Quantifier, Unary,
                  UnknownLit)
from .context import EvalContext
from .tri import Tri, tri_exists, tri_forall, tri_none

MAX_DEPTH = 64
MAX_REGEX_LEN = 256

IMO_HARMONIZED = {
    "SMC", "ISSC", "IOPP", "IAPP", "ISPP", "IAROPP", "ICPP", "ICEPP",
    "ILMC", "ILOMLC", "LOADLINE", "SAFETY_CONSTRUCTION", "SAFETY_EQUIPMENT",
    "SAFETY_RADIO", "CLC", "BUNKER", "WRECK_REMOVAL", "BWM", "MLC", "DA",
}
COC_ALIASES = {"COC", "COC_", "CERTIFICATE_OF_COMPETENCY", "COCP", "COP",
               "CERTIFICATE_OF_PROFICIENCY"}


class _Budget(Exception):
    pass


@dataclass
class EvalResult:
    tri: Tri
    unknown_reasons: list[str] = field(default_factory=list)
    value: Any = None


def _as_date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def _to_tri(v) -> Tri:
    if isinstance(v, Tri):
        return v
    if v is None:
        return Tri.UNKNOWN
    return Tri.of(v)


class Evaluator:
    def __init__(self, ctx: EvalContext):
        self.ctx = ctx
        self.steps = ctx.step_budget
        self.depth = 0
        self.reasons: list[str] = []
        self.bound: dict[str, Any] = {}

    # -- public ---------------------------------------------------------------
    def evaluate(self, expr: Expr) -> EvalResult:
        try:
            value = self._eval(expr)
            return EvalResult(_to_tri(value), self.reasons, value)
        except _Budget:
            self.reasons.append("step budget exhausted (sandbox)")
            return EvalResult(Tri.UNKNOWN, self.reasons, None)

    # -- core -----------------------------------------------------------------
    def _tick(self):
        self.steps -= 1
        if self.steps <= 0:
            raise _Budget()

    def _eval(self, node: Expr) -> Any:
        self._tick()
        self.depth += 1
        if self.depth > MAX_DEPTH:
            self.depth -= 1
            self.reasons.append("depth limit reached (sandbox)")
            return None
        try:
            if isinstance(node, Literal):
                return node.value
            if isinstance(node, UnknownLit):
                self.reasons.append("UNKNOWN literal")
                return None
            if isinstance(node, Path):
                return self._path(node)
            if isinstance(node, Unary):
                return _to_tri(self._eval(node.operand)).NOT()
            if isinstance(node, Binary):
                return self._binary(node)
            if isinstance(node, FuncCall):
                return self._call(node)
            if isinstance(node, Quantifier):
                return self._quantifier(node)
            raise TypeError(f"unknown node {node!r}")
        finally:
            self.depth -= 1

    def _note_missing(self, what: str):
        if len(self.reasons) < 32 and what not in self.reasons:
            self.reasons.append(f"missing fact: {what}")

    # -- paths -----------------------------------------------------------------
    def _path(self, node: Path) -> Any:
        cur: Any = _MISSING
        for i, part in enumerate(node.parts):
            if i == 0:
                if isinstance(part, Expr):
                    cur = self._eval(part)
                elif part in self.bound:
                    cur = self.bound[part]
                else:
                    cur = self.ctx.resolve_root(part)
                    if cur is None:
                        self._note_missing(part)
                        return None
                continue
            if isinstance(part, Expr):                      # index form a[expr]
                idx = self._eval(part)
                cur = self._index(cur, idx)
            else:
                cur = self._field(cur, part)
            if cur is _MISSING or cur is None:
                self._note_missing(".".join(str(p) for p in node.parts[:i + 1]))
                return None
        return None if cur is _MISSING else cur

    @staticmethod
    def _field(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, _MISSING)
        return getattr(obj, key, _MISSING)

    @staticmethod
    def _index(obj: Any, idx: Any) -> Any:
        try:
            if isinstance(obj, (list, tuple)) and isinstance(idx, (int, float)):
                return obj[int(idx)]
            if isinstance(obj, dict):
                return obj.get(idx, _MISSING)
            return _MISSING
        except (IndexError, KeyError, TypeError):
            return _MISSING

    # -- operators -------------------------------------------------------------
    def _binary(self, node: Binary) -> Any:
        op = node.op
        if op == "AND":
            return _to_tri(self._eval(node.left)).AND(_to_tri(self._eval(node.right)))
        if op == "OR":
            return _to_tri(self._eval(node.left)).OR(_to_tri(self._eval(node.right)))

        left = self._eval(node.left)
        right = self._eval(node.right)

        if op == "MATCHES":
            if left is None or right is None:
                return Tri.UNKNOWN
            if not isinstance(right, str) or len(right) > MAX_REGEX_LEN:
                self.reasons.append("MATCHES: unsafe/oversized pattern")
                return Tri.UNKNOWN
            try:
                return Tri.of(re.fullmatch(right, str(left)) is not None)
            except re.error:
                self.reasons.append("MATCHES: invalid pattern")
                return Tri.UNKNOWN

        if op == "IN":
            if left is None or right is None:
                return Tri.UNKNOWN
            if isinstance(right, (list, tuple, set, str)):
                return Tri.of(left in right)
            return Tri.of(left == right)

        if op in ("=", "!="):
            if left is None or right is None:
                return Tri.UNKNOWN
            eq = self._equals(left, right)
            return eq if op == "=" else eq.NOT()

        if op in ("<", "<=", ">", ">="):
            cmp = self._compare(left, right)
            if cmp is None:
                return Tri.UNKNOWN
            return Tri.of({"<": cmp < 0, "<=": cmp <= 0, ">": cmp > 0, ">=": cmp >= 0}[op])

        # arithmetic — total: division by zero => UNKNOWN
        if left is None or right is None:
            return None
        try:
            if op == "+":
                return float(left) + float(right)
            if op == "-":
                return float(left) - float(right)
            if op == "*":
                return float(left) * float(right)
            if op == "/":
                return float(left) / float(right) if float(right) != 0.0 else self._div_zero()
            if op == "%":
                return float(left) % float(right) if float(right) != 0.0 else self._div_zero()
        except (TypeError, ValueError):
            self.reasons.append(f"arithmetic {op} on non-numeric")
            return None
        raise TypeError(op)

    def _div_zero(self):
        self.reasons.append("division by zero => UNKNOWN")
        return None

    @staticmethod
    def _equals(left: Any, right: Any) -> Tri:
        ld, rd = _as_date(left), _as_date(right)
        if ld is not None and rd is not None:
            return Tri.of(ld == rd)
        if isinstance(left, bool) or isinstance(right, bool):
            return Tri.of(bool(left) == bool(right))
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return Tri.of(float(left) == float(right))
        return Tri.of(str(left) == str(right))

    @staticmethod
    def _compare(left: Any, right: Any) -> int | None:
        ld, rd = _as_date(left), _as_date(right)
        if ld is not None and rd is not None:
            return (ld > rd) - (ld < rd)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return (float(left) > float(right)) - (float(left) < float(right))
        if isinstance(left, str) and isinstance(right, str):
            return (left > right) - (left < right)
        return None

    # -- quantifiers ------------------------------------------------------------
    def _quantifier(self, node: Quantifier) -> Tri:
        source = self._resolve_source(node.source)
        if source is None:
            self._note_missing(f"quantifier source {node.source}")
            return Tri.UNKNOWN
        source = list(source)
        if not source:
            # Fail-closed asymmetry (documented): a universal over an empty /
            # unpopulated set cannot be *verified* => UNKNOWN, while EXISTS /
            # NONE over an empty set are definite negatives ("not on file").
            if node.kind == "FORALL":
                self.reasons.append(
                    f"quantifier source {node.source} empty — cannot verify universal")
                return Tri.UNKNOWN
            return Tri.FALSE if node.kind in ("EXISTS", "ANY") else Tri.TRUE
        results = []
        for item in source:
            self.bound[node.var] = item
            try:
                results.append(_to_tri(self._eval(node.body)))
            finally:
                self.bound.pop(node.var, None)
        if node.kind in ("EXISTS", "ANY"):
            return tri_exists(results)
        if node.kind == "FORALL":
            return tri_forall(results)
        if node.kind == "NONE":
            return tri_none(results)
        raise TypeError(node.kind)

    def _resolve_source(self, source: str):
        root = source.split(".")[0]
        if root in self.bound:
            val = self.bound[root]
        else:
            val = self.ctx.resolve_root(root)
        for part in source.split(".")[1:]:
            if val is None:
                return None
            val = self._field(val, part)
            if val is _MISSING:
                return None
        return val

    # -- builtin calls -----------------------------------------------------------
    def _call(self, node: FuncCall) -> Any:
        args = [self._eval(a) for a in node.args]
        if node.receiver is not None:
            recv = self._path(node.receiver)
            args.insert(0, recv)
        kwargs = {k: self._eval(v) for k, v in node.kwargs}
        impl = _BUILTINS.get(node.name)
        if impl is None:
            self.reasons.append(f"unknown function {node.name}")
            return None
        try:
            return impl(self, args, kwargs)
        except Exception as exc:  # totality: builtin failure folds to UNKNOWN
            self.reasons.append(f"{node.name} failed: {exc}")
            return None


_MISSING = object()


# ---------------------------------------------------------------------------
# Built-in functions (Part 9.3) — every one total, None => UNKNOWN
# ---------------------------------------------------------------------------

def _arg(args, i, default=None):
    return args[i] if i < len(args) else default


def _at(kwargs, args, i=0):
    """The 'at:' date argument, defaulting to the evaluation date."""
    v = kwargs.get("at", _arg(args, i))
    return _as_date(v) or None


def _is_true(v) -> bool | None:
    if v is None:
        return None
    return bool(v)


def _validity_window(cert: dict, at: date | None):
    """Return TRUE/FALSE/UNKNOWN for a cert valid at `at` (strict dates)."""
    if at is None:
        return Tri.UNKNOWN
    status = str(cert.get("verification_status", "UNVERIFIED")).upper()
    if status in ("REVOKED", "FORGED_SUSPECT"):
        return Tri.FALSE
    issue = _as_date(cert.get("issue_date"))
    expiry = _as_date(cert.get("expiry_date"))
    if issue is None and expiry is None:
        return Tri.UNKNOWN
    if issue is not None and at < issue:
        return Tri.FALSE
    if expiry is not None and at > expiry:
        return Tri.FALSE
    return Tri.TRUE


# --- temporal ---------------------------------------------------------------

def _in_force(ev: Evaluator, args, kwargs):
    if ev.ctx.in_force_fn is None:
        ev.reasons.append("resolver in_force unavailable")
        return None
    at = _at(kwargs, args, 1)
    if args[0] is None or at is None:
        return None
    return _is_true(ev.ctx.in_force_fn(str(args[0]), at))


def _version_at(ev: Evaluator, args, kwargs):
    if ev.ctx.version_at_fn is None:
        ev.reasons.append("resolver version_at unavailable")
        return None
    at = _at(kwargs, args, 1)
    if args[0] is None or at is None:
        return None
    return ev.ctx.version_at_fn(str(args[0]), at)


def _days_until(ev: Evaluator, args, kwargs):
    d = _as_date(args[0])
    return None if d is None else float((d - ev.ctx.eval_date).days)


def _expired(ev: Evaluator, args, kwargs):
    evd = args[0] if args else None
    if not isinstance(evd, dict):
        return Tri.UNKNOWN
    expiry = _as_date(evd.get("expiry_date"))
    at = _at(kwargs, args, 1) or ev.ctx.eval_date
    if expiry is None:
        ev.reasons.append("missing expiry_date")
        return Tri.UNKNOWN
    return Tri.of(expiry < at)


def _expires_within(ev: Evaluator, args, kwargs):
    evd, days = _arg(args, 0), _arg(args, 1)
    if not isinstance(evd, dict) or days is None:
        return Tri.UNKNOWN
    expiry = _as_date(evd.get("expiry_date"))
    at = ev.ctx.eval_date
    if expiry is None:
        ev.reasons.append("missing expiry_date")
        return Tri.UNKNOWN
    delta = (expiry - at).days
    return Tri.of(0 <= delta <= float(days))


# --- evidence ---------------------------------------------------------------

def _exists(ev: Evaluator, args, kwargs):
    etype, entity = _arg(args, 0), _arg(args, 1)
    eid = entity.get("id") if isinstance(entity, dict) else entity
    for e in ev.ctx.evidence:
        if str(e.get("evidence_type", "")).upper() == str(etype).upper() and \
           e.get("entity_id") in (eid, entity):
            return Tri.TRUE
    return Tri.FALSE


def _verified(ev: Evaluator, args, kwargs):
    evd = args[0] if args else None
    if not isinstance(evd, dict):
        return Tri.UNKNOWN
    status = str(evd.get("verification_status", "UNVERIFIED")).upper()
    return Tri.of(status == "VERIFIED")


def _issuer_matches(ev: Evaluator, args, kwargs):
    evd, registry = _arg(args, 0), _arg(args, 1)
    if not isinstance(evd, dict):
        return Tri.UNKNOWN
    issuer = evd.get("issuer")
    if issuer is None:
        ev.reasons.append("missing issuer")
        return Tri.UNKNOWN
    if isinstance(registry, (list, tuple, set)):
        return Tri.of(issuer in registry)
    if registry is None:
        return Tri.UNKNOWN
    return Tri.of(str(issuer) == str(registry))


# --- certificates -----------------------------------------------------------

def _cert_valid(ev: Evaluator, args, kwargs):
    ctype, entity = _arg(args, 0), _arg(args, 1)
    at = _at(kwargs, args, 2) or ev.ctx.eval_date
    certs = [c for c in ev.ctx.certs_for(entity)
             if str(c.get("type", c.get("cert_type", ""))).upper() == str(ctype).upper()]
    if not certs:
        return Tri.FALSE
    outcomes = [_validity_window(c, at) for c in certs]
    return tri_exists(outcomes)


def _cert_imo_harmonized(ev: Evaluator, args, kwargs):
    t = args[0] if args else None
    if t is None:
        return Tri.UNKNOWN
    return Tri.of(str(t).upper() in IMO_HARMONIZED)


# --- crew -------------------------------------------------------------------

def _coc_valid(ev: Evaluator, args, kwargs):
    member = args[0] if args else None
    if not isinstance(member, dict):
        ev.reasons.append("crew member unknown")
        return Tri.UNKNOWN
    at = _at(kwargs, args, 1) or ev.ctx.eval_date
    certs = [c for c in ev.ctx.certs_for(member)
             if str(c.get("type", c.get("cert_type", ""))).upper() in COC_ALIASES]
    if not certs:
        return Tri.FALSE
    return tri_exists(_validity_window(c, at) for c in certs)


def _rest_hours_compliant(ev: Evaluator, args, kwargs):
    member = _arg(args, 0)
    if not isinstance(member, dict):
        return Tri.UNKNOWN
    rest = member.get("rest_hours")
    if rest is None or "compliant" not in rest:
        ev.reasons.append("rest_hours data missing")
        return Tri.UNKNOWN
    return Tri.of(rest["compliant"])


# --- voyage / zone -----------------------------------------------------------

def _zone_at(ev: Evaluator, args, kwargs):
    if ev.ctx.zone_at_fn is None:
        ev.reasons.append("resolver zone_at unavailable")
        return None
    lat, lon = _arg(args, 0), _arg(args, 1)
    at = _at(kwargs, args, 2)
    if lat is None or lon is None or at is None:
        return None
    return ev.ctx.zone_at_fn(float(lat), float(lon), at)


def _leg_segments(ev: Evaluator, args, kwargs):
    voyage = _arg(args, 0) or ev.ctx.voyage
    if isinstance(voyage, dict):
        return voyage.get("legs") or []
    return []


def _annex_ratified(ev: Evaluator, args, kwargs):
    if ev.ctx.annex_ratified_fn is None:
        ev.reasons.append("resolver annex_ratified unavailable")
        return None
    flag, annex = _arg(args, 0), _arg(args, 1)
    at = _at(kwargs, args, 2) or ev.ctx.eval_date
    if flag is None or annex is None:
        return None
    return _is_true(ev.ctx.annex_ratified_fn(str(flag), str(annex), at))


# --- arithmetic / date --------------------------------------------------------

def _age_of(ev: Evaluator, args, kwargs):
    vessel = _arg(args, 0)
    at = _at(kwargs, args, 1) or ev.ctx.eval_date
    if not isinstance(vessel, dict):
        return None
    build = _as_date(vessel.get("build_date") or vessel.get("keel_laid_date"))
    return None if build is None else float((at - build).days) / 365.25


def _gt(ev: Evaluator, args, kwargs):
    vessel = _arg(args, 0)
    if not isinstance(vessel, dict):
        return None
    return vessel.get("gross_tonnage")


def _keel_laid_before(ev: Evaluator, args, kwargs):
    vessel, cutoff = _arg(args, 0), _as_date(_arg(args, 1))
    if not isinstance(vessel, dict) or cutoff is None:
        return Tri.UNKNOWN
    keel = _as_date(vessel.get("keel_laid_date"))
    if keel is None:
        ev.reasons.append("missing keel_laid_date")
        return Tri.UNKNOWN
    return Tri.of(keel < cutoff)


# --- jurisdiction --------------------------------------------------------------

def _layer_applies(ev: Evaluator, args, kwargs):
    if ev.ctx.layer_applies_fn is None:
        ev.reasons.append("resolver layer_applies unavailable")
        return None
    rule, segment = _arg(args, 0), _arg(args, 1)
    if rule is None or segment is None:
        return None
    return _is_true(ev.ctx.layer_applies_fn(str(rule),
                                           segment if isinstance(segment, str) else str(segment)))


def _precedence_max(ev: Evaluator, args, kwargs):
    values = _arg(args, 0)
    if not isinstance(values, (list, tuple, set)) or not values:
        return None
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    return max(nums) if nums else None


_BUILTINS = {
    "in_force": _in_force, "version_at": _version_at,
    "days_until": _days_until, "expired": _expired,
    "expires_within": _expires_within,
    "exists": _exists, "verified": _verified, "issuer_matches": _issuer_matches,
    "cert_valid": _cert_valid, "cert_imo_harmonized": _cert_imo_harmonized,
    "coc_valid": _coc_valid, "rest_hours_compliant": _rest_hours_compliant,
    "zone_at": _zone_at, "leg_segments": _leg_segments,
    "annex_ratified": _annex_ratified,
    "age_of": _age_of, "gt": _gt, "keel_laid_before": _keel_laid_before,
    "layer_applies": _layer_applies, "precedence_max": _precedence_max,
}


def evaluate(expr: Expr, ctx: EvalContext) -> EvalResult:
    return Evaluator(ctx).evaluate(expr)
