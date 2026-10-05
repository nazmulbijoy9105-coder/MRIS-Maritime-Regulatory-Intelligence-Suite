"""Corpus loader: manifest + rule YAML -> validated RuleSpec objects."""
from __future__ import annotations

import json
from pathlib import Path

from ..ilrmf import RuleSpec, parse_rule_spec

_CORPUS_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = _CORPUS_ROOT / "seed" / "manifest.json"
RULES_DIR = _CORPUS_ROOT / "rules"


def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_rules() -> dict[str, RuleSpec]:
    rules: dict[str, RuleSpec] = {}
    for path in sorted(RULES_DIR.glob("*.yaml")):
        spec = parse_rule_spec(path.read_text(encoding="utf-8"))
        rules[spec.rule_id] = spec
    return rules


def rule_file(rule_id: str) -> Path:
    return RULES_DIR / f"{rule_id}.yaml"
