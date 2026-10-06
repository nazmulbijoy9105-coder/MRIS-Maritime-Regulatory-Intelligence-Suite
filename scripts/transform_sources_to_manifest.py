import os
import json
from pathlib import Path

BASE_SOURCE_DIR = Path("data/raw_sources")
SEED_DIR = Path("mris/corpus/seed")
MANIFEST_PATH = SEED_DIR / "manifest.json"

def discover_instruments():
    instruments = []
    if not BASE_SOURCE_DIR.exists():
        return instruments
        
    for source_dir in BASE_SOURCE_DIR.iterdir():
        if not source_dir.is_dir():
            continue
            
        instrument_id = source_dir.name.replace("SRC-", "INT-")
        official_pdf = source_dir / "01_original" / "official_document.pdf"
        
        if official_pdf.exists():
            instruments.append({
                "instrument_id": instrument_id,
                "official_title": f"Instrument derived from {source_dir.name}",
                "status": "IN_FORCE",
                "verification_status": "REQUIRES_PRIMARY_VERIFICATION",
                "authoritative_sources": ["Local Raw Source"],
                "source_path": str(source_dir)
            })
    return instruments

def build_manifest():
    manifest = {
        "_metadata": {
            "version": "2.0-Enterprise-Registry",
            "last_updated": "2026-10-06",
            "description": "Canonical registry auto-generated from source directories."
        },
        "instruments": discover_instruments()
    }
    
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Manifest successfully written to {MANIFEST_PATH}")

if __name__ == "__main__":
    build_manifest()
