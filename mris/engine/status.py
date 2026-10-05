"""Status taxonomy + severity ordering (Part 9.7).

GREEN < YELLOW < RED < BLACK. Aggregation always takes the worst status.
"""
from __future__ import annotations

from enum import Enum


class Status(Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    BLACK = "BLACK"

    @property
    def severity(self) -> int:
        return _SEVERITY[self]

    def __lt__(self, other: "Status") -> bool:
        return self.severity < other.severity

    def __le__(self, other: "Status") -> bool:
        return self.severity <= other.severity


_SEVERITY = {
    Status.GREEN: 0,
    Status.YELLOW: 1,
    Status.RED: 2,
    Status.BLACK: 3,
}

_MEANING = {
    Status.GREEN: "all applicable obligations satisfied",
    Status.YELLOW: "compliant now, but expiring / missing non-critical evidence / advisory",
    Status.RED: "hard requirement failed",
    Status.BLACK: "conflict / missing data / unverified source / applicability uncertain",
}

_ACTION = {
    Status.GREEN: "none",
    Status.YELLOW: "scheduled action",
    Status.RED: "act before operation",
    Status.BLACK: "human review — system never guesses",
}


def worst(statuses) -> Status:
    statuses = list(statuses)
    if not statuses:
        return Status.BLACK   # no evidence either way => fail closed
    return max(statuses, key=lambda s: s.severity)


def meaning(status: Status) -> str:
    return _MEANING[status]


def customer_action(status: Status) -> str:
    return _ACTION[status]
