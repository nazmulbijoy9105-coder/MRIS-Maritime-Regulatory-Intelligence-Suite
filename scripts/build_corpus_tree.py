#!/usr/bin/env python3
"""Materialise the corpus directory tree (Blueprint v2.0 Part 4/5) from the
seed manifest. Each instrument gets its folder with the provision-atomic
layout; verification markers are preserved in metadata.json.

Usage:  python3 scripts/build_corpus_tree.py [output_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mris.corpus import load_manifest  # noqa: E402

BD_TREE = {
    "01_MERCHANT_SHIPPING": ["BD-ORD-MERCHANT-SHIPPING-1983", "BD-RULES-STCW-2011",
                             "BD-REG-MERCHANT-SHIPPING-RADIO-2002",
                             "BD-RULES-SEAMEN-RECRUITMENT-2001",
                             "BD-RULES-SEAMEN-RECRUITING-AGENT-LICENSE-2005"],
    "02_MARITIME_ZONES": ["BD-ACT-TERRITORIAL-WATERS-MARITIME-ZONES-1974",
                          "BD-AMEND-TERRITORIAL-WATERS-MARITIME-ZONES-2021"],
    "03_INLAND_SHIPPING": ["BD-ORD-INLAND-SHIPPING-1976", "BD-ORD-BIWT-AUTHORITY-1958",
                           "BD-ORD-PILOTAGE-1969"],
    "04_PORTS": ["BD-ACT-CHITTAGONG-PORT-AUTHORITY-2022",
                 "BD-ACT-MONGLA-PORT-AUTHORITY-2022",
                 "BD-ACT-PAYRA-PORT-AUTHORITY-2013"],
    "05_SHIP_RECYCLING": ["BD-ACT-SHIP-RECYCLING-2018"],
    "06_ENVIRONMENT": ["BD-ACT-ENVIRONMENT-CONSERVATION-1995",
                       "BD-RULES-ENVIRONMENT-CONSERVATION-2023",
                       "BD-RULES-AIR-POLLUTION-CONTROL-2022",
                       "BD-RULES-SOLID-WASTE-MANAGEMENT-2021",
                       "BD-RULES-E-WASTE-MANAGEMENT-2021",
                       "BD-RULES-HAZARDOUS-WASTE-SHIP-BREAKING-2011",
                       "BD-RULES-NOISE-POLLUTION-2025"],
}

SUBDIRS = ["original", "consolidated", "provisions", "amendments"]

INTL_TREE = {
    "IMO": ["IMO-CONV-SOLAS-1974", "IMO-CONV-COLREG-1972", "IMO-CONV-LOAD-LINES-1966",
            "IMO-CONV-TONNAGE-1969", "IMO-CONV-STCW-1978", "IMO-CONV-CSC-1972",
            "IMO-CONV-MARPOL-73-78", "IMO-CONV-BWM-2004", "IMO-CONV-AFS-2001",
            "IMO-CONV-BUNKER-2001", "IMO-CONV-WRECK-REMOVAL-2007", "IMO-CONV-HNS-1996",
            "IMO-CONV-SALVAGE-1989", "IMO-CONV-ATHENS-PAL-1974", "IMO-CONV-INTERVENTION-1969",
            "IMO-CONV-FACILITATION-1965", "IMO-CONV-SAR-1979", "IMO-CONV-TORREMOLINOS-1993"],
    "ILO": ["ILO-CONV-MLC-2006"],
    "UNCLOS": ["UNCLOS-1982"],
}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "corpus"
    manifest = load_manifest()
    by_id = {
        item["instrument_id"]: item
        for item in manifest["instruments"]
    }

    created = 0
    for section, ids in BD_TREE.items():
        for inst_id in ids:
            inst = by_id.get(inst_id, {"id": inst_id})
            base = out / "01_LEGAL_CORPUS" / "01_BANGLADESH" / section / inst_id
            for sub in SUBDIRS:
                (base / sub).mkdir(parents=True, exist_ok=True)
            (base / "metadata.json").write_text(
                json.dumps(inst, indent=2, ensure_ascii=False), encoding="utf-8")
            created += 1

    for org, ids in INTL_TREE.items():
        for inst_id in ids:
            inst = by_id.get(inst_id, {"id": inst_id})
            base = out / "01_LEGAL_CORPUS" / "02_INTERNATIONAL" / org / inst_id
            for sub in SUBDIRS:
                (base / sub).mkdir(parents=True, exist_ok=True)
            (base / "metadata.json").write_text(
                json.dumps(inst, indent=2, ensure_ascii=False), encoding="utf-8")
            created += 1

    # Part 4 top-level module folders (00_CORE .. 15_LIABILITY)
    for module in ["00_CORE/ontology", "00_CORE/jurisdictions", "00_CORE/authorities",
                   "00_CORE/legal_status", "00_CORE/source_types", "00_CORE/taxonomy",
                   "02_LEGAL_VERSION_CONTROL/verification", "03_RULE_ENGINE/dsl",
                   "04_ENTITY_ENGINE", "05_EVIDENCE_ENGINE", "06_COMPLIANCE_ENGINE",
                   "07_REGULATORY_CHANGE", "08_AUDIT", "09_APPLICATION",
                   "10_INFRA", "11_SHIPBUILDING", "12_SHIPYARD", "13_CYBER",
                   "14_INCIDENT", "15_LIABILITY"]:
        (out / module).mkdir(parents=True, exist_ok=True)

    print(f"corpus tree built under {out}: {created} instruments")


if __name__ == "__main__":
    main()
