"""ILRMF-DSL recursive-descent parser.

Grammar (EBNF, Part 9.3):
    expr        := or_expr
    or_expr     := and_expr ( "OR" and_expr )*
    and_expr    := not_expr ( "AND" not_expr )*
    not_expr    := "NOT" not_expr | quant_expr
    quant_expr  := ("EXISTS"|"FORALL"|"ANY"|"NONE") ident "IN" source ":" expr
                 | comparison
    comparison  := additive ( ("="|"!="|"<"|"<="|">"|">="|"IN"|"MATCHES") additive )?
    additive    := term ( ("+"|"-") term )*
    term        := factor ( ("*"|"/"|"%") factor )*
    factor      := literal | path | funcall | "(" expr ")" | "UNKNOWN"
    funcall     := [path "."] ident "(" [args] ")"
    args        := arg ("," arg)* ; arg := [ident ":"] expr

Sandbox constraints (Part 9.3): no I/O, no recursion beyond a fixed depth
cap, total on every input — enforced by the evaluator.
"""
from __future__ import annotations

from datetime import date

from .ast import (Binary, Expr, FuncCall, Literal, Path, Quantifier, Unary,
                  UnknownLit)
from .lexer import LexError, Token, tokenize

MAX_DEPTH = 64


class ParseError(SyntaxError):
    pass


class Parser:
    def __init__(self, text: str):
        self.text = text
        try:
            self.tokens = tokenize(text)
        except LexError as exc:
            raise ParseError(str(exc)) from exc
        self.i = 0
        self.depth = 0

    # -- token helpers --------------------------------------------------------
    def peek(self) -> Token:
        return self.tokens[self.i]

    def next(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, kind: str, value: str | None = None) -> Token:
        tok = self.peek()
        if tok.kind != kind or (value is not None and tok.value != value):
            raise ParseError(
                f"expected {kind}{':' + value if value else ''}, "
                f"got {tok.kind}:{tok.value!r} at position {tok.pos}")
        return self.next()

    def match(self, kind: str, value: str | None = None) -> bool:
        tok = self.peek()
        return tok.kind == kind and (value is None or tok.value == value)

    # -- entry ---------------------------------------------------------------
    def parse(self) -> Expr:
        expr = self.expr()
        if not self.match("EOF"):
            raise ParseError(f"unexpected trailing input {self.peek().value!r}")
        return expr

    def _guard(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError("expression nesting exceeds sandbox depth limit")

    # -- productions ----------------------------------------------------------
    def expr(self) -> Expr:
        self._guard()
        try:
            return self.or_expr()
        finally:
            self.depth -= 1

    def or_expr(self) -> Expr:
        left = self.and_expr()
        while self.match("KEYWORD", "OR"):
            self.next()
            left = Binary("OR", left, self.and_expr())
        return left

    def and_expr(self) -> Expr:
        left = self.not_expr()
        while self.match("KEYWORD", "AND"):
            self.next()
            left = Binary("AND", left, self.not_expr())
        return left

    def not_expr(self) -> Expr:
        if self.match("KEYWORD", "NOT"):
            self.next()
            return Unary("NOT", self.not_expr())
        return self.quant_expr()

    def quant_expr(self) -> Expr:
        tok = self.peek()
        if tok.kind == "KEYWORD" and tok.value in ("EXISTS", "FORALL", "ANY", "NONE"):
            kind = self.next().value
            var = self.expect("IDENT").value
            self.expect("KEYWORD", "IN")
            source = self._source()
            self.expect("PUNCT", ":")
            body = self.expr()
            return Quantifier(kind, var, source, body)
        return self.comparison()

    def _source(self) -> str:
        parts = [self.expect("IDENT").value]
        while self.match("PUNCT", "."):
            self.next()
            parts.append(self.expect("IDENT").value)
        return ".".join(parts)

    def comparison(self) -> Expr:
        left = self.additive()
        tok = self.peek()
        if (tok.kind == "OP" and tok.value in ("=", "!=", "<", "<=", ">", ">=")) or \
           (tok.kind == "KEYWORD" and tok.value in ("IN", "MATCHES")):
            op = self.next().value
            return Binary(op, left, self.additive())
        return left

    def additive(self) -> Expr:
        left = self.term()
        while self.match("OP", "+") or self.match("OP", "-"):
            op = self.next().value
            left = Binary(op, left, self.term())
        return left

    def term(self) -> Expr:
        left = self.factor()
        while self.peek().kind == "OP" and self.peek().value in ("*", "/", "%"):
            op = self.next().value
            left = Binary(op, left, self.factor())
        return left

    def factor(self) -> Expr:
        tok = self.peek()

        if tok.kind == "KEYWORD" and tok.value == "UNKNOWN":
            self.next()
            return UnknownLit()

        if tok.kind == "PUNCT" and tok.value == "(":
            self.next()
            inner = self.expr()
            self.expect("PUNCT", ")")
            return inner

        if tok.kind == "NUM":
            self.next()
            return Literal(float(tok.value), "NUMBER")

        if tok.kind == "STR":
            self.next()
            return Literal(tok.value, "STRING")

        if tok.kind == "DATE":
            self.next()
            return Literal(date.fromisoformat(tok.value), "DATE")

        if tok.kind == "KEYWORD" and tok.value in ("TRUE", "FALSE"):
            self.next()
            return Literal(tok.value == "TRUE", "BOOL")

        if tok.kind == "IDENT":
            return self._ident_expr()

        raise ParseError(f"unexpected token {tok.kind}:{tok.value!r} at position {tok.pos}")

    def _ident_expr(self) -> Expr:
        """path | funcall | method-call: a.b.c(...)"""
        head = self.expect("IDENT").value
        parts: list = [head]
        receiver: Path | None = None

        while self.match("PUNCT", "."):
            # lookahead: '.' ident, then '(' => method call on the path so far
            if self.tokens[self.i + 1].kind == "IDENT" and \
               self.tokens[self.i + 2].kind == "PUNCT" and \
               self.tokens[self.i + 2].value == "(":
                self.next()  # '.'
                name = self.expect("IDENT").value
                receiver = Path(tuple(parts))
                args, kwargs = self._call_args()
                return FuncCall(name=name, args=args, kwargs=kwargs, receiver=receiver)
            self.next()  # '.'
            parts.append(self.expect("IDENT").value)

        # index suffixes: path[expr]
        while self.match("PUNCT", "["):
            self.next()
            idx = self.expr()
            self.expect("PUNCT", "]")
            parts.append(idx)

        if self.match("PUNCT", "("):
            args, kwargs = self._call_args()
            return FuncCall(name=parts[-1] if len(parts) == 1 else ".".join(str(p) for p in parts),
                            args=args, kwargs=kwargs)

        return Path(tuple(parts))

    def _call_args(self):
        self.expect("PUNCT", "(")
        args: list[Expr] = []
        kwargs: list[tuple[str, Expr]] = []
        if not self.match("PUNCT", ")"):
            while True:
                # named arg? IDENT ':' expr
                if self.peek().kind == "IDENT" and \
                   self.tokens[self.i + 1].kind == "PUNCT" and \
                   self.tokens[self.i + 1].value == ":":
                    name = self.next().value
                    self.next()  # ':'
                    kwargs.append((name, self.expr()))
                else:
                    args.append(self.expr())
                if self.match("PUNCT", ","):
                    self.next()
                    continue
                break
        self.expect("PUNCT", ")")
        return tuple(args), tuple(kwargs)


def parse_expression(text: str) -> Expr:
    return Parser(text).parse()
