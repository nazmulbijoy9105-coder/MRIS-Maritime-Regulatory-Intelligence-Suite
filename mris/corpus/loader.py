import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SEED_DIR = BASE_DIR / "seed"
RULES_DIR = BASE_DIR / "rules"
MANIFEST_PATH = SEED_DIR / "manifest.json"

def load_manifest():
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found at {MANIFEST_PATH}")
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_rules():
    rules = []
    if RULES_DIR.exists():
        for rule_path in RULES_DIR.glob("*.json"):
            with open(rule_path, "r", encoding="utf-8") as f:
                rules.append(json.load(f))
    return rules

def rule_file(rule_id):
    rule_path = RULES_DIR / f"{rule_id}.json"
    if not rule_path.exists():
        raise FileNotFoundError(f"Rule file {rule_id} not found at {rule_path}")
    with open(rule_path, "r", encoding="utf-8") as f:
        return json.load(f)
