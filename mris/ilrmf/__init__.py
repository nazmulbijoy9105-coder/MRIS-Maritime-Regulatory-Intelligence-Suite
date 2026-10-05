"""ILRMF-DSL — Maritime Legal Rule Modelling Framework expression language.

Public surface: parse_expression, evaluate, RuleSpec, Tri, EvalContext.
"""
from .context import EvalContext
from .evaluator import EvalResult, evaluate
from .parser import ParseError, parse_expression
from .rule_spec import (ADVISORY, MANDATORY, RuleSpec, RuleSpecError,
                        definition_json, parse_rule_spec)
from .tri import Tri
from .types import TypeCheckError, TypeChecker

__all__ = [
    "EvalContext", "EvalResult", "evaluate", "parse_expression", "ParseError",
    "RuleSpec", "RuleSpecError", "parse_rule_spec", "definition_json",
    "Tri", "TypeChecker", "TypeCheckError", "MANDATORY", "ADVISORY",
]
