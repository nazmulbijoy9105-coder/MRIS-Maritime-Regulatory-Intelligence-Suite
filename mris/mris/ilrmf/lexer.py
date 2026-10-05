"""ILRMF-DSL tokenizer.

Token grammar notes (Part 9.3):
  - date literals: #YYYY-MM-DD  (avoids ambiguity with subtraction)
  - strings: 'single' or "double" quoted
  - numbers: 123, 12.5
  - BOOL: TRUE | FALSE | UNKNOWN
  - keywords: AND OR NOT EXISTS FORALL ANY NONE IN MATCHES
  - named args in calls: name: expr   (e.g. coc_valid(crew_member, at: eval_date))
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class LexError(SyntaxError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str      # NUM STR DATE BOOL IDENT OP PUNCT KEYWORD EOF
    value: str
    pos: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.kind}:{self.value}"


KEYWORDS = {"AND", "OR", "NOT", "EXISTS", "FORALL", "ANY", "NONE", "IN",
            "MATCHES", "TRUE", "FALSE", "UNKNOWN"}

# longest-first so '<=' beats '<'
OPS = ["!=", "<=", ">=", "=", "<", ">", "+", "-", "*", "/", "%"]

_TOKEN_RE = re.compile(r"""
    (?P<WS>\s+)
  | (?P<DATE>\#[0-9]{4}-[0-9]{2}-[0-9]{2})
  | (?P<NUM>[0-9]+(?:\.[0-9]+)?)
  | (?P<STR>'[^']*'|\"[^\"]*\")
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP>!=|<=|>=|=|<|>|\+|-|\*|/|%)
  | (?P<PUNCT>[()\[\]{},:.])
""", re.VERBOSE)


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise LexError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = m.lastgroup
        value = m.group()
        pos = m.end()
        if kind == "WS":
            continue
        if kind == "IDENT" and value.upper() in KEYWORDS:
            tokens.append(Token("KEYWORD", value.upper(), m.start()))
        elif kind == "DATE":
            tokens.append(Token("DATE", value[1:], m.start()))
        elif kind == "STR":
            tokens.append(Token("STR", value[1:-1], m.start()))
        else:
            tokens.append(Token(kind, value, m.start()))
    tokens.append(Token("EOF", "", len(text)))
    return tokens
