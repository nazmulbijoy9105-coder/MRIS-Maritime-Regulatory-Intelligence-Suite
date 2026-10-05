"""LCA-1 — Layer-Combining Algorithm for multi-jurisdiction voyages (Part 9.6).

For each voyage_leg x jurisdiction_segment:
    1. segment the voyage (input: legs with zone_type / coastal_state / port)
    2. collect candidate rules per layer (L1 flag treaty position via
       state_participation, L2 flag law, L3 coastal where zone qualifies,
       L4 port law at port calls, L5 class, L6 contractual)
    3. resolve applicability per rule against segment facts
    4. group by obligation dimension
    5. combine: compatible => STRICTER; incompatible => CONFLICT => BLACK
       item citing both provisions + layers (legal review, 48 h SLA)
    6. aggregate to voyage result: worst status across legs with per-leg
       drill-down

PSC asymmetry (encoded): for a foreign-flag vessel, L4 enforcement is modelled
as inspection against L1+L2 certificates + L4 entry conditions; for a domestic
vessel L4 applies in full as binding law.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .precedence import (CombinedResult, Constraint, DimensionResult, Layer,
                         Obligation, combine_obligations)
from .rules import RuleOutcome, execute_rule, match_applicability
from .status import Status, worst
from ..ilrmf import EvalContext, RuleSpec, Tri

LEGAL_REVIEW_SLA_HOURS = 48

# zone types that bring L3 coastal-state law into play (§9.6 step 2)
COASTAL_ZONES = {"TERRITORIAL", "CONTIGUOUS", "EEZ", "CONTINENTAL_SHELF"}


@dataclass
class RuleCandidate:
    """A rule (or static obligation) that may apply on some voyage segments."""
    rule_id: str
    layer: Layer
    dimension: str                       # obligation dimension for grouping
    requirement: str
    provision_ids: list[str]
    rule_version_id: str
    legal_version_id: str
    jurisdiction_id: Optional[str] = None   # None = universal (e.g. IMO layer)
    applicability: dict = field(default_factory=dict)
    constraint: Optional[Constraint] = None    # parameterised obligation
    spec: Optional[RuleSpec] = None            # DSL condition, if executable


@dataclass
class Segment:
    layer: Layer
    jurisdiction_id: str
    as_of_date: date


@dataclass
class Leg:
    seq: int
    zone_type: str                       # INTERNAL_WATERS|TERRITORIAL|...|HIGH_SEAS
    coastal_state: Optional[str]
    port: Optional[str] = None
    segments: list[Segment] = field(default_factory=list)
    facts: dict = field(default_factory=dict)   # leg-specific facts


@dataclass
class LegResult:
    leg_seq: int
    zone_type: str
    combined: CombinedResult
    outcomes: list[RuleOutcome] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def status(self) -> Status:
        return self.combined.status

    @property
    def conflicts(self):
        return [d.conflict for d in self.combined.dimensions.values() if d.conflict]


@dataclass
class VoyageResult:
    legs: list[LegResult]
    overall_status: Status
    conflict_items: list[dict]
    drill_down: dict


def _segments_for_leg(leg: Leg, voyage_as_of: date) -> list[Segment]:
    """Default segment derivation when none are supplied (§9.6 steps 1-2)."""
    if leg.segments:
        return leg.segments
    segs = [Segment(Layer.L1_INTL, "INTL", voyage_as_of)]
    segs.append(Segment(Layer.L2_FLAG, "FLAG", voyage_as_of))
    if leg.zone_type in COASTAL_ZONES and leg.coastal_state:
        segs.append(Segment(Layer.L3_COASTAL, leg.coastal_state, voyage_as_of))
    if leg.port:
        segs.append(Segment(Layer.L4_PORT, leg.port, voyage_as_of))
    segs.append(Segment(Layer.L5_CLASS, "CLASS", voyage_as_of))
    segs.append(Segment(Layer.L6_CONTRACT, "CONTRACT", voyage_as_of))
    return segs


def _candidate_applies(candidate: RuleCandidate, segment: Segment,
                       leg: Leg, vessel_flag: str, domestic: bool) -> Tri:
    """Layer gate + PSC asymmetry + applicability predicate."""
    if candidate.layer is not segment.layer:
        return Tri.FALSE
    if candidate.jurisdiction_id is not None and \
            candidate.jurisdiction_id != segment.jurisdiction_id:
        return Tri.FALSE

    # PSC asymmetry: L4 is entry-conditions-only for foreign-flag vessels
    if candidate.layer is Layer.L4_PORT and not domestic:
        entry_only = candidate.applicability.get("psc_entry_only", False)
        if not entry_only:
            return Tri.FALSE

    # 'psc_entry_only' is an engine marker, not a fact dimension
    applicability = {k: v for k, v in candidate.applicability.items()
                     if k != "psc_entry_only"}
    facts = {
        "zone_type": leg.zone_type,
        "coastal_state": leg.coastal_state,
        "port": leg.port,
        "flag": vessel_flag,
        "domestic": domestic,
        **leg.facts,
    }
    return match_applicability(applicability, facts)


def resolve_leg(leg: Leg, candidates: list[RuleCandidate], *,
                vessel_flag: str, domestic: bool,
                as_of: date, ctx: EvalContext) -> LegResult:
    segments = _segments_for_leg(leg, as_of)
    obligations: list[Obligation] = []
    outcomes: list[RuleOutcome] = []
    skipped: list[str] = []

    for segment in segments:
        for candidate in candidates:
            applies = _candidate_applies(candidate, segment, leg,
                                         vessel_flag, domestic)
            if applies is Tri.FALSE:
                continue
            if applies is Tri.UNKNOWN:
                obligations.append(Obligation(
                    dimension=candidate.dimension, layer=candidate.layer,
                    provision_ids=candidate.provision_ids,
                    rule_id=candidate.rule_id,
                    rule_version_id=candidate.rule_version_id,
                    legal_version_id=candidate.legal_version_id,
                    requirement=candidate.requirement,
                    status=Status.BLACK,
                    reason=f"{candidate.rule_id}: applicability uncertain on "
                           f"leg {leg.seq} ({leg.zone_type})",
                ))
                continue

            status, reason = Status.GREEN, candidate.requirement
            if candidate.spec is not None:
                outcome = execute_rule(candidate.spec, ctx,
                                       rule_version_id=candidate.rule_version_id,
                                       applicability_facts={})
                outcomes.append(outcome)
                status, reason = outcome.status, outcome.reason

            obligations.append(Obligation(
                dimension=candidate.dimension, layer=candidate.layer,
                provision_ids=candidate.provision_ids,
                rule_id=candidate.rule_id,
                rule_version_id=candidate.rule_version_id,
                legal_version_id=candidate.legal_version_id,
                requirement=candidate.requirement,
                constraint=candidate.constraint, status=status, reason=reason,
            ))
            skipped.append(candidate.rule_id)   # evaluated (for drill-down)

    combined = combine_obligations(obligations)
    return LegResult(leg_seq=leg.seq, zone_type=leg.zone_type,
                     combined=combined, outcomes=outcomes, skipped=skipped)


def resolve_voyage(legs: list[Leg], candidates: list[RuleCandidate], *,
                   vessel_flag: str, domestic: bool = False,
                   as_of: Optional[date] = None,
                   ctx: Optional[EvalContext] = None) -> VoyageResult:
    as_of = as_of or (ctx.eval_date if ctx else date.today())
    ctx = ctx or EvalContext(eval_date=as_of)

    leg_results = [resolve_leg(leg, candidates, vessel_flag=vessel_flag,
                               domestic=domestic, as_of=as_of, ctx=ctx)
                   for leg in legs]

    conflict_items = []
    for lr in leg_results:
        for conflict in lr.conflicts:
            conflict_items.append({
                "type": "CONFLICT",
                "dimension": conflict.dimension,
                "leg_seq": lr.leg_seq,
                "zone_type": lr.zone_type,
                "status": Status.BLACK.value,
                "left": {"rule_id": conflict.left.rule_id,
                         "layer": conflict.left.layer.code,
                         "provision_ids": conflict.left.provision_ids,
                         "requirement": conflict.left.requirement},
                "right": {"rule_id": conflict.right.rule_id,
                          "layer": conflict.right.layer.code,
                          "provision_ids": conflict.right.provision_ids,
                          "requirement": conflict.right.requirement},
                "action": "routed to legal review queue",
                "sla_hours": LEGAL_REVIEW_SLA_HOURS,
            })

    overall = worst(lr.status for lr in leg_results) if leg_results else Status.BLACK
    drill_down = {
        str(lr.leg_seq): {
            "zone_type": lr.zone_type,
            "status": lr.status.value,
            "dimensions": {
                dim: {
                    "status": d.status.value,
                    "merged_requirement": d.merged_requirement,
                    "constraint": (None if d.constraint is None
                                   else {"kind": d.constraint.kind,
                                         "value": list(d.constraint.value)
                                         if isinstance(d.constraint.value, frozenset)
                                         else d.constraint.value}),
                    "binding": [o.rule_id for o in d.binding],
                    "advisory": [o.rule_id for o in d.advisory],
                    "conflict": d.conflict is not None,
                }
                for dim, d in lr.combined.dimensions.items()
            },
        }
        for lr in leg_results
    }

    return VoyageResult(legs=leg_results, overall_status=overall,
                        conflict_items=conflict_items, drill_down=drill_down)
