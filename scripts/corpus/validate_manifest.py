import json
import sys
from pathlib import Path

MANIFEST_PATH = Path("mris/corpus/seed/manifest.json")

def run():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    errors = []
    valid_statuses = ["IN_FORCE", "PLANNED", "NEW", "DISCOVERY_PLACEHOLDER"]
    valid_verifications = ["VERIFIED_AGAINST_GAZETTE", "REQUIRES_PRIMARY_VERIFICATION", "TO_BE_GAZETTE_IDENTIFIED"]
    
    for inst in manifest.get("instruments", []):
        if inst.get("status") not in valid_statuses:
            errors.append(f"{inst['instrument_id']} has invalid status: {inst.get('status')}")
        if inst.get("verification_status") not in valid_verifications:
            errors.append(f"{inst['instrument_id']} has invalid verification_status: {inst.get('verification_status')}")
        if inst.get("status") == "DISCOVERY_PLACEHOLDER" and inst.get("evaluation_eligibility") is not False:
            errors.append(f"{inst['instrument_id']} is placeholder but evaluation_eligibility is not False")
            
    if errors:
        print("LC-02 Manifest Audit: FAILED")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)
    else:
        print("LC-02 Manifest Audit: PASSED")

if __name__ == "__main__":
    run()
