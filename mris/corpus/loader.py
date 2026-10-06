import json
import os
from pathlib import Path

# Package-relative paths (works when data is included in package)
BASE_DIR = Path(__file__).resolve().parent
SEED_DIR = BASE_DIR / "seed"
RULES_DIR = BASE_DIR / "rules"
MANIFEST_PATH = SEED_DIR / "manifest.json"


def _find_manifest() -> Path:
    """Search for manifest in multiple locations (package, project root, env)."""
    candidates = [
        MANIFEST_PATH,
        Path(os.getcwd()) / "mris" / "corpus" / "seed" / "manifest.json",
        Path(os.getcwd()) / "corpus" / "seed" / "manifest.json",
    ]
    env_root = os.environ.get("MRIS_CORPUS_ROOT")
    if env_root:
        candidates.append(Path(env_root) / "seed" / "manifest.json")
    for path in candidates:
        if path.exists():
            return path
    return MANIFEST_PATH


def _find_rules_dir() -> Path:
    """Search for rules directory in multiple locations."""
    candidates = [
        RULES_DIR,
        Path(os.getcwd()) / "mris" / "corpus" / "rules",
        Path(os.getcwd()) / "corpus" / "rules",
    ]
    env_root = os.environ.get("MRIS_CORPUS_ROOT")
    if env_root:
        candidates.append(Path(env_root) / "rules")
    for path in candidates:
        if path.exists() and path.is_dir():
            return path
    return RULES_DIR


def load_manifest():
    """Loads the canonical registry of legal instruments."""
    path = _find_manifest()
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rules():
    """Loads YAML rule files as RuleSpec objects (executable rules only).
    Returns dict keyed by rule_id."""
    rules = {}
    rules_dir = _find_rules_dir()
    if not rules_dir.exists():
        return rules

    try:
        from mris.ilrmf.rule_spec import parse_rule_spec
    except ImportError:
        parse_rule_spec = None

    # Load YAML rules through parse_rule_spec (returns RuleSpec objects)
    for rule_path in sorted(rules_dir.glob("*.yaml")):
        try:
            text = rule_path.read_text(encoding="utf-8")
            if parse_rule_spec:
                spec = parse_rule_spec(text)
                rules[spec.rule_id] = spec
            else:
                import yaml
                data = yaml.safe_load(text)
                if data and "rule_id" in data:
                    rules[data["rule_id"]] = data
        except Exception:
            continue

    # Also load JSON rules as dicts (metadata only, don't override YAML)
    for rule_path in sorted(rules_dir.glob("*.json")):
        try:
            with open(rule_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rid = data.get("rule_id", rule_path.stem)
            if rid not in rules:
                rules[rid] = data
        except Exception:
            continue

    return rules


def rule_file(rule_id):
    """Returns the Path to a rule file (YAML or JSON)."""
    rules_dir = _find_rules_dir()
    for ext in [".yaml", ".json"]:
        rule_path = rules_dir / f"{rule_id}{ext}"
        if rule_path.exists():
            return rule_path
    raise FileNotFoundError(f"Rule file {rule_id} not found in {rules_dir}")
