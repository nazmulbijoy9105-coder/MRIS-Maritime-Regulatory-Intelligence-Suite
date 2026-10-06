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


def _find_aliases() -> Path:
    """Search for instrument_aliases.json."""
    candidates = [
        SEED_DIR / "instrument_aliases.json",
        Path(os.getcwd()) / "mris" / "corpus" / "seed" / "instrument_aliases.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return SEED_DIR / "instrument_aliases.json"


def load_manifest():
    """Loads the canonical registry of legal instruments."""
    path = _find_manifest()
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_rules():
    """Loads all rule files from the rules directory as a dict keyed by rule_id."""
    rules = {}
    rules_dir = _find_rules_dir()
    if rules_dir.exists():
        for rule_path in sorted(rules_dir.glob("*.json")):
            with open(rule_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rid = data.get("rule_id", rule_path.stem)
            rules[rid] = data
    return rules


def rule_file(rule_id):
    """Loads a specific rule file by its ID."""
    rules_dir = _find_rules_dir()
    rule_path = rules_dir / f"{rule_id}.json"
    if not rule_path.exists():
        rule_path = rules_dir / f"{rule_id}.yaml"
        if not rule_path.exists():
            raise FileNotFoundError(f"Rule file {rule_id} not found at {rules_dir}")
        import yaml
        with open(rule_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    with open(rule_path, "r", encoding="utf-8") as f:
        return json.load(f)
