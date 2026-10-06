"""Corpus loader: manifest + rule YAML -> validated RuleSpec objects."""
from __future__ import annotations

import json
from pathlib import Path

from ..ilrmf import RuleSpec, parse_rule_spec

_CORPUS_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = _CORPUS_ROOT / "seed" / "manifest.json"
RULES_DIR = _CORPUS_ROOT / "rules"

# Non-executable YAML artifacts that must never enter the legal rule registry.
_EXCLUDED_RULE_FILENAMES = {
    "TEMPLATE-ENTERPRISE-RULE.yaml",
}


def load_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _rule_paths() -> list[Path]:
    """Return executable rule YAML files recursively.

    Templates and other explicitly excluded artifacts are never loaded.
    """
    return sorted(
        path
        for path in RULES_DIR.rglob("*.yaml")
        if path.name not in _EXCLUDED_RULE_FILENAMES
    )


def load_rules() -> dict[str, RuleSpec]:
    """Load and validate all executable corpus rule specifications."""
    rules: dict[str, RuleSpec] = {}

    for path in _rule_paths():
        spec = parse_rule_spec(path.read_text(encoding="utf-8"))

        if spec.rule_id in rules:
            raise ValueError(
                f"duplicate executable rule_id {spec.rule_id!r}: "
                f"{path}"
            )

        rules[spec.rule_id] = spec

    return rules


def rule_file(rule_id: str) -> Path:
    """Resolve an executable rule ID to its canonical YAML file."""
    matches = sorted(
        path
        for path in RULES_DIR.rglob(f"{rule_id}.yaml")
        if path.name not in _EXCLUDED_RULE_FILENAMES
    )

    if not matches:
        raise FileNotFoundError(
            f"executable corpus rule not found: {rule_id}"
        )

    if len(matches) > 1:
        raise ValueError(
            f"multiple executable corpus files found for rule_id "
            f"{rule_id!r}: {matches}"
        )

    return matches[0]
