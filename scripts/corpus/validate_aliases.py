"""
MRIS — LC-02 INSTRUMENT IDENTITY AUDIT
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mris.corpus.resolver import (
    InstrumentResolver,
    UnknownInstrumentReference,
    BrokenAliasReference,
    AliasChainError,
)

CONTROLLED_ALIAS_TYPES = {"FORMAL_LEGAL_ID", "LEGACY_ID", "RULE_INSTRUMENT_ID", "SOURCE_IDENTIFIER", "EXTERNAL_REGISTRY_ID", "HISTORICAL_IDENTIFIER"}

def audit(manifest_path: Path, aliases_path: Path) -> int:
    print("=" * 62)
    print("MRIS — LC-02 INSTRUMENT IDENTITY AUDIT")
    print("=" * 62)
    errors = []
    warnings = []
    try: resolver = InstrumentResolver(manifest_path, aliases_path)
    except Exception as e:
        print(f"FATAL: resolver failed to load: {type(e).__name__}: {e}")
        return 1

    print(f"CANONICAL INSTRUMENTS : {len(resolver.canonical_ids)}")
    print(f"ALIASES               : {len(resolver.alias_keys)}")
    print()

    # [1] TARGET EXISTENCE
    broken = []
    for alias in resolver.alias_keys:
        try: resolver.resolve(alias)
        except Exception: broken.append(alias)
    if broken:
        print(f"[1] FAIL — {len(broken)} broken targets")
        for b in broken: errors.append(f"Broken alias target: {b}")
    else: print("[1] PASS — 0 broken targets")
    print()

    # [6] ALIAS TYPES
    bad_types = [(a, rec.get("alias_type")) for a, rec in resolver._aliases.items() if rec.get("alias_type") not in CONTROLLED_ALIAS_TYPES]
    if bad_types:
        print(f"[6] FAIL — {len(bad_types)} uncontrolled alias_type values")
    else: print("[6] PASS — all controlled values")
    print()

    # [8] PLACEHOLDER / DRAFT WARNINGS
    placeholders = [iid for iid, rec in resolver._canonical.items() if "to be identified" in (rec.get("notes") or "").lower() or "to be identified" in (rec.get("official_title") or "").lower()]
    if placeholders:
        print(f"[8] WARN — {len(placeholders)} discovery placeholders found")
        for p in placeholders: print(f"    - {p}")
    else: print("[8] PASS — no discovery placeholders found")
    print()

    print("=" * 62)
    if errors:
        print(f"[CRITICAL ERRORS]: {len(errors)}")
        for e in errors: print(f"  - {e}")
        print("STRUCTURALLY INVALID")
        return 1

    print("STRUCTURALLY VALID")
    print("FREEZE: NOT YET")
    return 0

if __name__ == "__main__":
    seed = Path("mris/corpus/seed")
    sys.exit(audit(seed / "manifest.json", seed / "instrument_aliases.json"))
