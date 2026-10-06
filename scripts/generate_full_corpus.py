import json
from pathlib import Path

MANIFEST_PATH = Path("mris/corpus/seed/manifest.json")
RULES_DIR = Path("mris/corpus/rules")
RULES_DIR.mkdir(parents=True, exist_ok=True)

# [id, title, formal_id, type, status, verification, notes, primary_rule_id]
int_data = [
    ("INT-M01", "SOLAS 1974", "IMO-CONV-SOLAS-1974", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Safety of life at sea", ""),
    ("INT-M02", "SOLAS 1988 Protocol", "IMO-PROT-SOLAS-1988", "PROTOCOL", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "SOLAS amendments", ""),
    ("INT-M03", "Load Lines 1966", "IMO-CONV-LOADLINES-1966", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Load line certification", ""),
    ("INT-M04", "Load Lines 1988 Protocol", "IMO-PROT-LOADLINES-1988", "PROTOCOL", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Load line protocol", ""),
    ("INT-M05", "COLREG 1972", "IMO-CONV-COLREG-1972", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Collision regulations", ""),
    ("INT-M06", "STCW 1978", "IMO-CONV-STCW-1978", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Training & watchkeeping", ""),
    ("INT-M07", "MARPOL 73/78", "IMO-CONV-MARPOL-73-78", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Pollution prevention", "IMO-CONV-MARPOL-73-78-ANI-REG36-R001"),
    ("INT-M08", "MARPOL Annex I", "IMO-ANNEX-MARPOL-I", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Oil pollution", "IMO-CONV-MARPOL-73-78-ANI-REG36-R001"),
    ("INT-M09", "MARPOL Annex II", "IMO-ANNEX-MARPOL-II", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "NLS in bulk", ""),
    ("INT-M10", "MARPOL Annex III", "IMO-ANNEX-MARPOL-III", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Harmful substances packaged", ""),
    ("INT-M11", "MARPOL Annex IV", "IMO-ANNEX-MARPOL-IV", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Sewage", ""),
    ("INT-M12", "MARPOL Annex V", "IMO-ANNEX-MARPOL-V", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Garbage", "IMO-CONV-MARPOL-73-78-ANV-REG10-R001"),
    ("INT-M13", "MARPOL Annex VI", "IMO-ANNEX-MARPOL-VI", "ANNEX", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Air pollution", "IMO-CONV-MARPOL-73-78-ANVI-REG6-R001"),
    ("INT-M14", "BWM 2004", "IMO-CONV-BWM-2004", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Ballast water management", ""),
    ("INT-M15", "AFS 2001", "IMO-CONV-AFS-2001", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Anti-fouling systems", ""),
    ("INT-M16", "Hong Kong Convention 2009", "IMO-CONV-HONGKONG-2009", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Ship recycling", ""),
    ("INT-M17", "MLC 2006", "ILO-CONV-MLC-2006", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Maritime labour", ""),
    ("INT-M18", "UNCLOS 1982", "UN-CONV-UNCLOS-1982", "CONVENTION", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Law of the sea", ""),
    ("INT-M19", "LLMC 1976", "IMO-CONV-LLMC-1976", "CONVENTION", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Limitation of liability (BD NON_PARTY)", ""),
    ("INT-M20", "Bunker 2001", "IMO-CONV-BUNKER-2001", "CONVENTION", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Bunker oil liability", "IMO-CONV-BUNKER-2001-ART07-R001"),
    ("INT-M21", "Nairobi WRC 2007", "IMO-CONV-NAIROBI-WRC-2007", "CONVENTION", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Wreck removal", "IMO-CONV-NAIROBI-WRC-2007-ART05-R001"),
    ("INT-M22", "ISM Code", "IMO-CODE-ISM", "CODE", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Safety management", ""),
    ("INT-M23", "ISPS Code", "IMO-CODE-ISPS", "CODE", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Ship & port facility security", ""),
    ("INT-M24", "SUA Convention 1988", "IMO-CONV-SUA-1988", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Unlawful acts", "IMO-CONV-SUA-1988-ART03-R001"),
    ("INT-M25", "SUA Protocol 1988", "IMO-PROT-SUA-PLATFORM-1988", "PROTOCOL", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Offences against fixed platforms", "IMO-PROT-SUA-PLATFORM-1988-ART02-R001"),
    ("INT-M26", "STPS Agreement 1971", "IMO-AGREE-STPS-1971", "AGREEMENT", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Special trade passenger ships", "IMO-AGREE-STPS-1971-REG01-R001"),
    ("INT-M27", "STPS Protocol 1973", "IMO-PROT-STPS-SPACE-1973", "PROTOCOL", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Space requirements for STPS", "IMO-PROT-STPS-SPACE-1973-REG01-R001"),
    ("INT-M28", "IMSO Convention 1976", "IMO-CONV-IMSO-1976", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Mobile satellite organisation", "IMO-CONV-IMSO-1976-ART03-R001"),
    ("INT-M29", "INMARSAT Agreement 1976", "IMO-AGREE-INMARSAT-1976", "AGREEMENT", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "INMARSAT system operation", "IMO-AGREE-INMARSAT-1976-ART03-R001"),
    ("INT-M30", "CLC 1992", "IMO-CONV-CLC-1992", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Civil liability for oil pollution", "IMO-CONV-CLC-1992-ART07-R001"),
    ("INT-M31", "FUND 1992", "IMO-CONV-FUND-1992", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Oil pollution compensation fund", "IMO-CONV-FUND-1992-ART04-R001"),
    ("INT-M32", "HNS Convention 2010", "IMO-CONV-HNS-2010", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Hazardous & noxious substances", "IMO-CONV-HNS-2010-ART12-R001"),
    ("INT-M33", "OPRC 1990", "IMO-CONV-OPRC-1990", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Oil pollution preparedness", "IMO-CONV-OPRC-1990-ART03-R001"),
    ("INT-M34", "OPRC-HNS Protocol 2000", "IMO-PROT-OPRC-HNS-2000", "PROTOCOL", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "HNS pollution preparedness", "IMO-PROT-OPRC-HNS-2000-ART03-R001"),
    ("INT-M35", "Salvage Convention 1989", "IMO-CONV-SALVAGE-1989", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Salvage operations & rewards", "IMO-CONV-SALVAGE-1989-ART08-R001"),
    ("INT-M36", "Tonnage Convention 1969", "IMO-CONV-TONNAGE-1969", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Tonnage measurement", "IMO-CONV-TONNAGE-1969-ART06-R001"),
    ("INT-M37", "FAL Convention 1965", "IMO-CONV-FAL-1965", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Facilitation of maritime traffic", "IMO-CONV-FAL-1965-STD2-R001"),
    ("INT-M38", "CSC 1972", "IMO-CONV-CSC-1972", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Container safety", "IMO-CONV-CSC-1972-ART04-R001"),
    ("INT-M39", "Intervention Convention 1969", "IMO-CONV-INTERVENTION-1969", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Intervention on high seas", "IMO-CONV-INTERVENTION-1969-ART01-R001"),
    ("INT-M40", "London Convention 1972", "IMO-CONV-LONDON-1972", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Prevention of marine dumping", "IMO-CONV-LONDON-1972-ART04-R001"),
    ("INT-M41", "Athens Convention 1974", "IMO-CONV-ATHENS-1974", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Passenger liability", "IMO-CONV-ATHENS-1974-ART04-R001"),
    ("INT-M42", "Arrest Convention 1999", "IMO-CONV-ARREST-1999", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Arrest of ships", "IMO-CONV-ARREST-1999-ART01-R001"),
    ("INT-M43", "Maritime Liens & Mortgages 1993", "IMO-CONV-LIENS-1993", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Maritime liens & mortgages", "IMO-CONV-LIENS-1993-ART04-R001"),
    ("INT-M44", "Collision Convention 1910", "IMO-CONV-COLLISION-1910", "CONVENTION", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Collision liability", "IMO-CONV-COLLISION-1910-ART03-R001"),
    ("INT-M45", "LLMC Protocol 1996", "IMO-PROT-LLMC-1996", "PROTOCOL", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Updated limitation amounts", "IMO-PROT-LLMC-1996-ART01-R001"),
    ("INT-M48", "Cape Town Agreement 2012", "IMO-AGREE-CAPETOWN-2012", "AGREEMENT", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Fishing vessel safety", "IMO-AGREE-CAPETOWN-2012-CH2-R001"),
    ("INT-M49", "SFV / Torremolinos Protocol 1993", "IMO-PROT-SFV-1993", "PROTOCOL", "PLANNED", "REQUIRES_PRIMARY_VERIFICATION", "Fishing vessel safety", "IMO-PROT-SFV-1993-CH3-R001"),
    ("INT-M50", "SAR Convention 1979", "IMO-CONV-SAR-1979", "CONVENTION", "NEW", "REQUIRES_PRIMARY_VERIFICATION", "Search & rescue services", "IMO-CONV-SAR-1979-CH2-R001"),
    ("INT-M51", "GMDSS / SOLAS Chapter IV", "IMO-GMDSS-SOLAS-CHIV", "CHAPTER", "NEW", "REQUIRES_PRIMARY_VERIFICATION", "Global Maritime Distress & Safety System", "IMO-GMDSS-SOLAS-CHIV-REG01-R001")
]

# [id, title, type, status, verification, notes, primary_rule_id]
bd_data = [
    ("BD-M01", "Merchant Shipping Ordinance 1983", "ORDINANCE", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "4 live rules", "BD-ORD-MERCHANT-SHIPPING-1983-S066-R001"),
    ("BD-M02", "Inland Shipping Ordinance 1976", "ORDINANCE", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "", ""),
    ("BD-M03", "Chattogram Port Authority Act 2022", "ACT", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Repealed 1976 Ordinance", ""),
    ("BD-M04", "Mongla Port Authority Act 2022", "ACT", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Repealed 1976 Ordinance", ""),
    ("BD-M05", "Payra Port Authority Act 2013", "ACT", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Subordinate SIs still missing", ""),
    ("BD-M06", "Pilotage Ordinance 1969", "ORDINANCE", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "Inland waters scope", ""),
    ("BD-M07", "Bangladesh Environment Conservation Act 1995", "ACT", "IN_FORCE", "VERIFIED_AGAINST_GAZETTE", "", ""),
    ("BD-M08", "Environment Conservation Rules 2023", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Parent: BD-M07", ""),
    ("BD-M09", "Air Pollution (Control) Rules 2022", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M10", "Ship Breaking and Ship Recycling Rules 2011", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Implements INT-M16", ""),
    ("BD-M11", "Seamen Recruitment Rules 2001", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M12", "Seamen Recruiting Agent (License) Rules 2005", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M13", "Merchant Shipping (Radio) Regulations 2002", "REGULATIONS", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Implements INT-M01 / GMDSS", ""),
    ("BD-M14", "Officers & Ratings Training Certification Rules 2011", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Implements INT-M06", ""),
    ("BD-M15", "Merchant Shipping Levy Collection Rules 2013", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M16", "Bangladesh Flag Vessels (Protection) Act 2019", "ACT", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M17", "Bangladesh Flag Vessels (Protection) Rules 2023", "RULES", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Parent: BD-M16", ""),
    ("BD-M18", "Bangladesh Lighthouse Act 2020", "ACT", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "", ""),
    ("BD-M19", "Territorial Waters and Maritime Zones Act 1974", "ACT", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Implements INT-M18", ""),
    ("BD-M20", "Territorial Waters and Maritime Zones Amendment Act 2021", "ACT", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Parent: BD-M19", ""),
    ("BD-M21", "Bangladesh Shipping Corporation Act 2017", "ACT", "IN_FORCE", "REQUIRES_PRIMARY_VERIFICATION", "Repealed 1972 Order", ""),
    ("BD-M22", "Payra Port subordinate rules (TBD)", "RULES", "NEW", "TO_BE_GAZETTE_IDENTIFIED", "Complete Payra instrument set", ""),
    ("BD-M23", "Domestic ISPS / port-security implementation", "RULES", "NEW", "TO_BE_GAZETTE_IDENTIFIED", "National ISPS implementation", ""),
    ("BD-M24", "Additional MSO 1983 subordinate SIs", "RULES", "NEW", "TO_BE_GAZETTE_IDENTIFIED", "Remaining MSO secondary legislation", ""),
    ("BD-M25", "Further environmental SIs under BECA", "RULES", "NEW", "TO_BE_GAZETTE_IDENTIFIED", "Additional env compliance", "")
]

rules = [
    ("BD-ORD-MERCHANT-SHIPPING-1983-S066-R001", "LICENCE", "BD-ORD-MERCHANT-SHIPPING-1983", "BD-M01", "S66 Licence to sail", "L2", "ACTIVE"),
    ("BD-ORD-MERCHANT-SHIPPING-1983-S082-R001", "MANNING", "BD-ORD-MERCHANT-SHIPPING-1983", "BD-M01", "S82 Manning", "L2", "ACTIVE"),
    ("BD-ORD-MERCHANT-SHIPPING-1983-S335-R001", "LOADLINE", "BD-ORD-MERCHANT-SHIPPING-1983", "BD-M01", "S335 Load Line Cert", "L2", "ACTIVE"),
    ("BD-ORD-MERCHANT-SHIPPING-1983-S350-R001", "UNSEAWORTHY", "BD-ORD-MERCHANT-SHIPPING-1983", "BD-M01", "S350 Unseaworthy", "L2", "ACTIVE"),
    ("IMO-CONV-MARPOL-73-78-ANI-REG36-R001", "MARPOL", "IMO-CONV-MARPOL-73-78", "INT-M07", "Annex I Reg 36 Oil Record Book", "L1/L2", "ACTIVE"),
    ("IMO-CONV-MARPOL-73-78-ANV-REG10-R001", "MARPOL", "IMO-CONV-MARPOL-73-78", "INT-M07", "Annex V Reg 10 Garbage", "L1/L2", "ACTIVE"),
    ("IMO-CONV-MARPOL-73-78-ANVI-REG6-R001", "MARPOL", "IMO-CONV-MARPOL-73-78", "INT-M07", "Annex VI Reg 6 IAPP", "L1/L2", "ACTIVE"),
    ("IMO-CONV-SUA-1988-ART03-R001", "UNLAWFUL_ACTS", "IMO-CONV-SUA-1988", "INT-M24", "Art 3 Offences", "L1/L2/L3/L4", "PLANNED"),
    ("IMO-CONV-SUA-1988-ART06-R001", "JURISDICTION", "IMO-CONV-SUA-1988", "INT-M24", "Art 6 Jurisdiction", "L3/L4", "PLANNED"),
    ("IMO-CONV-SUA-1988-ART10-R001", "EXTRADITION", "IMO-CONV-SUA-1988", "INT-M24", "Art 10 Extradition", "L2/L4", "PLANNED"),
    ("IMO-CONV-SAR-1979-CH2-R001", "SAR", "IMO-CONV-SAR-1979", "INT-M50", "Ch 2 Organisation of SAR", "L1/L2/L3", "PLANNED"),
    ("IMO-GMDSS-SOLAS-CHIV-REG01-R001", "GMDSS", "IMO-GMDSS-SOLAS-CHIV", "INT-M51", "Ch IV Radio installations", "L2", "PLANNED"),
    ("IMO-CONV-TONNAGE-1969-ART06-R001", "TONNAGE", "IMO-CONV-TONNAGE-1969", "INT-M36", "Art 6 ITC", "L2", "PLANNED"),
    ("IMO-CONV-FAL-1965-STD2-R001", "FACILITATION", "IMO-CONV-FAL-1965", "INT-M37", "Std 2 Arrival docs", "L2/L4", "PLANNED"),
    ("IMO-CONV-OPRC-1990-ART03-R001", "PREPAREDNESS", "IMO-CONV-OPRC-1990", "INT-M33", "Art 3 Emergency plans", "L2/L3/L4", "PLANNED"),
    ("IMO-CONV-CLC-1992-ART07-R001", "LIABILITY", "IMO-CONV-CLC-1992", "INT-M30", "Art 7 Compulsory insurance", "L2/L4", "PLANNED")
]

instruments = []
for row in int_data:
    instruments.append({
        "instrument_id": row[0], "jurisdiction": "INTL", "instrument_type": row[3], "official_title": row[1],
        "short_name": row[1], "formal_id": row[2], "status": row[4], "verification_status": row[5],
        "notes": row[6], "primary_rule_id": row[7] if len(row) > 7 and row[7] else None
    })

for row in bd_data:
    instruments.append({
        "instrument_id": row[0], "jurisdiction": "BD", "instrument_type": row[2], "official_title": row[1],
        "short_name": row[1], "status": row[3], "verification_status": row[4],
        "notes": row[5], "primary_rule_id": row[6] if len(row) > 6 and row[6] else None
    })

manifest = {
    "_metadata": {
        "version": "2.0-Enterprise-Registry",
        "last_updated": "2026-10-06",
        "description": "Canonical registry of legal instruments."
    },
    "instruments": instruments
}

with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest successfully written to {MANIFEST_PATH} with {len(instruments)} instruments.")

for r in rules:
    rule_data = {
        "rule_id": r[0], "domain": r[1], "formal_instrument_id": r[2], "canonical_id": r[3],
        "focus": r[4], "layer": r[5], "status": r[6]
    }
    file_path = RULES_DIR / f"{r[0]}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(rule_data, f, indent=2)
print(f"Successfully written {len(rules)} rule files to {RULES_DIR}.")
