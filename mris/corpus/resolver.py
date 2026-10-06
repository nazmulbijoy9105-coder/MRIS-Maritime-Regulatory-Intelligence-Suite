"""
MRIS LC-02 — Deterministic Instrument Identity Resolver
"""
from __future__ import annotations
import json
from pathlib import Path

class UnknownInstrumentReference(Exception): pass
class BrokenAliasReference(Exception): pass
class AliasChainError(Exception): pass
class AmbiguousInstrumentReference(Exception): pass

class InstrumentResolver:
    def __init__(self, manifest_path: Path | str, aliases_path: Path | str):
        self.manifest_path = Path(manifest_path)
        self.aliases_path = Path(aliases_path)
        with open(self.manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        with open(self.aliases_path, encoding="utf-8") as f:
            alias_data = json.load(f)
        self._canonical = {}
        for inst in manifest.get("instruments", []):
            iid = inst.get("instrument_id")
            if not iid: raise ValueError("Manifest record missing instrument_id")
            if iid in self._canonical: raise ValueError(f"Duplicate canonical instrument_id: {iid}")
            self._canonical[iid] = inst
        self._aliases = {}
        for alias, record in alias_data.get("aliases", {}).items():
            if not isinstance(record, dict) or "instrument_id" not in record:
            target = record["instrument_id"]
            if target not in self._canonical: raise BrokenAliasReference(alias, target)
            self._aliases[alias] = record

    @property
    def canonical_ids(self): return set(self._canonical)
    @property
    def alias_keys(self): return set(self._aliases)

    def resolve(self, value: str) -> str:
        if not isinstance(value, str) or not value.strip(): raise UnknownInstrumentReference(value)
        if value in self._canonical: return value
        record = self._aliases.get(value)
        if record is None: raise UnknownInstrumentReference(value)
        target = record["instrument_id"]
        if target not in self._canonical: raise BrokenAliasReference(value, target)
        return target

    def get(self, value: str) -> dict:
        canonical = self.resolve(value)
        return self._canonical[canonical]

    def aliases_for(self, canonical_id: str) -> list[str]:
        if canonical_id not in self._canonical: raise UnknownInstrumentReference(canonical_id)
        return sorted(a for a, r in self._aliases.items() if r["instrument_id"] == canonical_id)

    def is_canonical(self, value: str) -> bool: return value in self._canonical
    def is_alias(self, value: str) -> bool: return value in self._aliases

def default_resolver(corpus_seed: Path | str = "mris/corpus/seed") -> InstrumentResolver:
    seed = Path(corpus_seed)
    return InstrumentResolver(manifest_path=seed / "manifest.json", aliases_path=seed / "instrument_aliases.json")

if __name__ == "__main__":
    r = default_resolver()
    tests = ["INT-M01", "IMO-CONV-SOLAS-1974", "BD-M01", "BD-ORD-MERCHANT-SHIPPING-1983", "UNKNOWN-XYZ"]
    print("LC-02 resolver self-test")
    print("=" * 60)
    for t in tests:
    print("=" * 60)
    print(f"Canonical IDs : {len(r.canonical_ids)}")
    print(f"Aliases       : {len(r.alias_keys)}")
