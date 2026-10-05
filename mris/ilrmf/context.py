"""Evaluation context — the facts an ILRMF-DSL rule is evaluated against.

Data contract (all dict-based, JSONB-friendly):
    vessel:      {name, imo_number, flag, gross_tonnage, ship_type,
                  keel_laid_date, build_date, ...}
    crew:        [{id, rank, certificates: [{type, issue_date, expiry_date,
                  verification_status}], rest_hours: {...}}]
    evidence:    [{evidence_type, entity_type, entity_id, issuer,
                  issue_date, expiry_date, verification_status}]
    certificates:[same shape as crew certificates + entity_id]
    voyage:      {legs: [{zone_type, coastal_state, ...}]}
    eval_date:   date — the "relevant date" of the determination

Resolvers (fail-closed: absent resolver => UNKNOWN, never a guess):
    in_force(provision_id, at)      -> bool | None
    version_at(instrument_id, at)   -> str  | None
    annex_ratified(flag, annex, at) -> bool | None
    zone_at(lat, lon, at)           -> str  | None
    layer_applies(rule, segment)    -> bool | None
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Optional


@dataclass
class EvalContext:
    eval_date: date
    facts: dict[str, Any] = field(default_factory=dict)
    crew: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    certificates: list[dict] = field(default_factory=list)
    voyage: dict[str, Any] = field(default_factory=dict)

    # optional resolvers — None means "unknown" (fail-closed)
    in_force_fn: Optional[Callable[[str, date], Optional[bool]]] = None
    version_at_fn: Optional[Callable[[str, date], Optional[str]]] = None
    annex_ratified_fn: Optional[Callable[[str, str, date], Optional[bool]]] = None
    zone_at_fn: Optional[Callable[[float, float, date], Optional[str]]] = None
    layer_applies_fn: Optional[Callable[[str, str], Optional[bool]]] = None

    # sandbox budget
    step_budget: int = 10_000

    # -- lookup helpers ------------------------------------------------------
    def resolve_root(self, name: str):
        if name == "eval_date":
            return self.eval_date
        if name == "current_crew":
            return self.crew
        if name == "evidence":
            return self.evidence
        if name == "certificates":
            return self.certificates
        if name == "voyage":
            return self.voyage
        return self.facts.get(name)

    def crew_of(self, entity) -> list[dict]:
        return self.crew

    def evidence_for(self, entity) -> list[dict]:
        eid = entity.get("id") or entity.get("imo_number") if isinstance(entity, dict) else entity
        out = [e for e in self.evidence
               if e.get("entity_id") in (eid, entity if isinstance(entity, str) else None)]
        return out

    def certs_for(self, entity) -> list[dict]:
        if isinstance(entity, dict) and "certificates" in entity:
            return entity["certificates"] or []
        eid = entity.get("id") if isinstance(entity, dict) else entity
        return [c for c in self.certificates if c.get("entity_id") == eid]
