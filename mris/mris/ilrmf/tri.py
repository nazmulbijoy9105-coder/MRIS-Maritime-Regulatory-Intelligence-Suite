"""Three-valued (Kleene) logic — the fail-closed heart of ILRMF-DSL.

TRUE / FALSE / UNKNOWN. UNKNOWN arises from missing facts, unverified sources
or applicability uncertainty. In a MANDATORY rule UNKNOWN => BLACK
(blueprint Part 9.3). NOT UNKNOWN = UNKNOWN.
"""
from __future__ import annotations

from enum import Enum


class Tri(Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

    # ---- Kleene connectives -------------------------------------------------
    def AND(self, other: "Tri") -> "Tri":
        if self is Tri.FALSE or other is Tri.FALSE:
            return Tri.FALSE
        if self is Tri.UNKNOWN or other is Tri.UNKNOWN:
            return Tri.UNKNOWN
        return Tri.TRUE

    def OR(self, other: "Tri") -> "Tri":
        if self is Tri.TRUE or other is Tri.TRUE:
            return Tri.TRUE
        if self is Tri.UNKNOWN or other is Tri.UNKNOWN:
            return Tri.UNKNOWN
        return Tri.FALSE

    def NOT(self) -> "Tri":
        return {Tri.TRUE: Tri.FALSE, Tri.FALSE: Tri.TRUE, Tri.UNKNOWN: Tri.UNKNOWN}[self]

    # ---- helpers ------------------------------------------------------------
    @property
    def is_true(self) -> bool:
        return self is Tri.TRUE

    @property
    def is_unknown(self) -> bool:
        return self is Tri.UNKNOWN

    @classmethod
    def of(cls, value) -> "Tri":
        """Coerce a Python value into the three-valued domain."""
        if isinstance(value, Tri):
            return value
        if value is None:
            return Tri.UNKNOWN
        return Tri.TRUE if bool(value) else Tri.FALSE


# Kleene quantifier reductions over a stream of Tri --------------------------

def tri_exists(values) -> Tri:
    """TRUE if any TRUE; FALSE if all FALSE; else UNKNOWN."""
    saw_unknown = False
    for v in values:
        v = Tri.of(v)
        if v is Tri.TRUE:
            return Tri.TRUE
        if v is Tri.UNKNOWN:
            saw_unknown = True
    return Tri.UNKNOWN if saw_unknown else Tri.FALSE


def tri_forall(values) -> Tri:
    """TRUE if all TRUE; FALSE if any FALSE; else UNKNOWN."""
    saw_unknown = False
    for v in values:
        v = Tri.of(v)
        if v is Tri.FALSE:
            return Tri.FALSE
        if v is Tri.UNKNOWN:
            saw_unknown = True
    return Tri.UNKNOWN if saw_unknown else Tri.TRUE


def tri_none(values) -> Tri:
    """TRUE if all FALSE; FALSE if any TRUE; else UNKNOWN."""
    return tri_exists(values).NOT()
