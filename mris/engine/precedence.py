"""Precedence hierarchy + conflict resolution (Parts 9.1, 9.5).

L1 International treaty  -> Binding
L2 Flag-State legislation -> Binding
L3 Coastal-State          -> Binding within zone
L4 Port-State law/rules   -> Binding in/at port
L5 Class (delegated)      -> Binding via delegation
L6 Contractual / commercial -> ADVISORY / YELLOW only

Operators:
    STRICTER(a, b)  merge of compatible constraints on one obligation dimension
    CONFLICT(p1,p2) mutually incompatible hard obligations => BLACK + legal review
    ADVISORY(x)     L6 wrapper — can only produce YELLOW, never weaken statutory

Invariant (Principle 15): an advisory item can never flip a statutory GREEN
lower; a binding item always dominates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .status import Status, worst


class Layer(Enum):
    L1_INTL = ("L1", "International treaty obligations", True)
    L2_FLAG = ("L2", "Flag-State legislation & regulations", True)
    L3_COASTAL = ("L3", "Coastal-State legislation", True)
    L4_PORT = ("L4", "Port-State law + port authority rules", True)
    L5_CLASS = ("L5", "Class statutory requirements (delegated)", True)
    L6_CONTRACT = ("L6", "Contractual / commercial (SIRE, OCIMF, charter party)", False)

    def __init__(self, code: str, description: str, binding: bool):
        self.code = code
        self.description = description
        self.binding = binding

    @classmethod
    def from_code(cls, code: str) -> "Layer":
        for layer in cls:
            if layer.code == code or layer.name == code:
                return layer
        raise ValueError(f"unknown layer {code!r}")


# ---------------------------------------------------------------------------
# Parameterised constraints — what STRICTER/CONFLICT operate on
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Constraint:
    """MIN(v): must be >= v (higher = stricter).
       MAX(v): must be <= v (lower = stricter).
       SET(vs): must be one of vs (smaller = stricter)."""
    kind: str                      # MIN | MAX | SET
    value: Any

    @staticmethod
    def min(v: float) -> "Constraint":
        return Constraint("MIN", float(v))

    @staticmethod
    def max(v: float) -> "Constraint":
        return Constraint("MAX", float(v))

    @staticmethod
    def one_of(*values) -> "Constraint":
        return Constraint("SET", frozenset(values))

    def satisfies(self, v) -> bool:
        if self.kind == "MIN":
            return v >= self.value
        if self.kind == "MAX":
            return v <= self.value
        return v in self.value


def stricter(a: Constraint, b: Constraint) -> Optional[Constraint]:
    """STRICTER intersection of two constraints on the same dimension.

    Returns the tighter constraint, or None when they are mutually
    incompatible (that caller turns into CONFLICT).
    """
    if a.kind == "MIN" and b.kind == "MIN":
        return Constraint.min(max(a.value, b.value))
    if a.kind == "MAX" and b.kind == "MAX":
        return Constraint.max(min(a.value, b.value))
    if a.kind == "SET" and b.kind == "SET":
        common = a.value & b.value
        return Constraint("SET", common) if common else None
    if {a.kind, b.kind} == {"MIN", "MAX"}:
        lo = a if a.kind == "MIN" else b
        hi = a if a.kind == "MAX" else b
        return lo if lo.value <= hi.value else None   # MIN(8) vs MAX(7) => conflict
    # SET vs MIN/MAX: keep both by satisfaction check on the intersection
    if {a.kind, b.kind} == {"SET", "MIN"}:
        s, m = (a, b) if a.kind == "SET" else (b, a)
        kept = frozenset(v for v in s.value if v >= m.value)
        return Constraint("SET", kept) if kept else None
    if {a.kind, b.kind} == {"SET", "MAX"}:
        s, m = (a, b) if a.kind == "SET" else (b, a)
        kept = frozenset(v for v in s.value if v <= m.value)
        return Constraint("SET", kept) if kept else None
    return None


# ---------------------------------------------------------------------------
# Obligations
# ---------------------------------------------------------------------------

@dataclass
class Obligation:
    dimension: str                       # e.g. "manning_level", "sewage_discharge"
    layer: Layer
    provision_ids: list[str]
    rule_id: str
    rule_version_id: str
    legal_version_id: str
    requirement: str                     # human-readable requirement text
    constraint: Optional[Constraint] = None
    status: Status = Status.GREEN        # pass/fail status when no constraint
    reason: str = ""
    required_action: Optional[str] = None
    deadline: Optional[str] = None


@dataclass
class Conflict:
    dimension: str
    left: Obligation
    right: Obligation

    @property
    def provision_ids(self) -> list[str]:
        return self.left.provision_ids + self.right.provision_ids


@dataclass
class DimensionResult:
    dimension: str
    constraint: Optional[Constraint]
    merged_requirement: str
    binding: list[Obligation] = field(default_factory=list)
    advisory: list[Obligation] = field(default_factory=list)
    conflict: Optional[Conflict] = None

    @property
    def status(self) -> Status:
        if self.conflict is not None:
            return Status.BLACK
        statuses = [o.status for o in self.binding]
        if self.constraint is not None and statuses:
            return worst(statuses)
        return worst(statuses) if statuses else Status.GREEN


@dataclass
class CombinedResult:
    dimensions: dict[str, DimensionResult]

    @property
    def status(self) -> Status:
        """Binding statuses only — advisory can never lower a GREEN (P15)."""
        binding = [d.status for d in self.dimensions.values() if d.binding]
        return worst(binding) if binding else Status.GREEN

    @property
    def advisory_items(self) -> list[Obligation]:
        out = []
        for d in self.dimensions.values():
            out.extend(d.advisory)
        return out


def combine_obligations(obligations: list[Obligation]) -> CombinedResult:
    """Group by obligation dimension; STRICTER-merge compatible binding
    constraints; CONFLICT on incompatible ones; keep advisory separate."""
    by_dim: dict[str, list[Obligation]] = {}
    for ob in obligations:
        by_dim.setdefault(ob.dimension, []).append(ob)

    dimensions: dict[str, DimensionResult] = {}
    for dim, obs in by_dim.items():
        binding = [o for o in obs if o.layer.binding]
        advisory = [o for o in obs if not o.layer.binding]

        merged: Optional[Constraint] = None
        conflict: Optional[Conflict] = None
        parts: list[str] = []
        for ob in binding:
            parts.append(ob.requirement)
            if ob.constraint is None:
                continue
            if merged is None:
                merged = ob.constraint
                continue
            tighter = stricter(merged, ob.constraint)
            if tighter is None:
                conflict = Conflict(dim, binding[0], ob)
                merged = None
                break
            merged = tighter

        dimensions[dim] = DimensionResult(
            dimension=dim,
            constraint=merged,
            merged_requirement="; ".join(parts),
            binding=binding,
            advisory=advisory,
            conflict=conflict,
        )
    return CombinedResult(dimensions)
