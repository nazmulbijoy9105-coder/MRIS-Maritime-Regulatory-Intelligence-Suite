"""ILRMF-DSL AST nodes + JSON serialisation (rule_version.definition JSONB)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional, Union


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Literal:
    value: Any                       # float | str | bool | date
    type: str                        # NUMBER | STRING | BOOL | DATE


@dataclass(frozen=True)
class UnknownLit:
    """The UNKNOWN literal."""


@dataclass(frozen=True)
class Path:
    """vessel.flag, crew_member.rank, evidence[type] ... parts: str | Expr."""
    parts: tuple

    @staticmethod
    def parse(raw: str) -> "Path":
        return Path(tuple(raw.split(".")))


@dataclass(frozen=True)
class FuncCall:
    name: str
    args: tuple = ()                                   # positional exprs
    kwargs: tuple = ()                                 # ((name, expr), ...)
    receiver: Optional[Path] = None                    # method-style: crew_member.coc_valid(...)


@dataclass(frozen=True)
class Unary:
    op: str                                            # NOT
    operand: "Expr"


@dataclass(frozen=True)
class Binary:
    op: str                                            # AND OR = != < <= > >= IN MATCHES + - * / %
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True)
class Quantifier:
    kind: str                                          # EXISTS | FORALL | ANY | NONE
    var: str
    source: str                                        # current_crew | evidence | certificates | voyage.legs | ...
    body: "Expr"


Expr = Union[Literal, UnknownLit, Path, FuncCall, Unary, Binary, Quantifier]


# ---------------------------------------------------------------------------
# JSON (JSONB) serialisation — round-trippable
# ---------------------------------------------------------------------------

def to_json(node: Expr) -> dict:
    if isinstance(node, Literal):
        v = node.value
        if isinstance(v, date):
            v = v.isoformat()
        return {"node": "literal", "type": node.type, "value": v}
    if isinstance(node, UnknownLit):
        return {"node": "unknown"}
    if isinstance(node, Path):
        return {"node": "path", "parts": [p if isinstance(p, str) else to_json(p) for p in node.parts]}
    if isinstance(node, FuncCall):
        return {
            "node": "call", "name": node.name,
            "args": [to_json(a) for a in node.args],
            "kwargs": {k: to_json(v) for k, v in node.kwargs},
            "receiver": to_json(node.receiver) if node.receiver else None,
        }
    if isinstance(node, Unary):
        return {"node": "unary", "op": node.op, "operand": to_json(node.operand)}
    if isinstance(node, Binary):
        return {"node": "binary", "op": node.op,
                "left": to_json(node.left), "right": to_json(node.right)}
    if isinstance(node, Quantifier):
        return {"node": "quantifier", "kind": node.kind, "var": node.var,
                "source": node.source, "body": to_json(node.body)}
    raise TypeError(f"cannot serialise {node!r}")


def from_json(data: dict) -> Expr:
    kind = data.get("node")
    if kind == "literal":
        t, v = data["type"], data["value"]
        if t == "DATE":
            v = date.fromisoformat(v)
        elif t == "NUMBER":
            v = float(v)
        return Literal(v, t)
    if kind == "unknown":
        return UnknownLit()
    if kind == "path":
        return Path(tuple(p if isinstance(p, str) else from_json(p) for p in data["parts"]))
    if kind == "call":
        recv = data.get("receiver")
        return FuncCall(
            name=data["name"],
            args=tuple(from_json(a) for a in data.get("args", [])),
            kwargs=tuple((k, from_json(v)) for k, v in data.get("kwargs", {}).items()),
            receiver=from_json(recv) if recv else None,
        )
    if kind == "unary":
        return Unary(data["op"], from_json(data["operand"]))
    if kind == "binary":
        return Binary(data["op"], from_json(data["left"]), from_json(data["right"]))
    if kind == "quantifier":
        return Quantifier(data["kind"], data["var"], data["source"], from_json(data["body"]))
    raise ValueError(f"unknown AST node kind {kind!r}")
