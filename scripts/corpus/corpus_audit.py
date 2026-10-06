import json
import sys
from pathlib import Path

MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "mris"
    / "corpus"
    / "seed"
    / "manifest.json"
)

INSTRUMENT_ID_PREFIXES = ("INT-", "BD-")

REQUIRED_FIELDS = [
    "instrument_id",
    "jurisdiction",
    "instrument_type",
    "official_title",
    "short_name",
    "status",
    "verification_status",
]

INTERNATIONAL_ONLY_FIELDS = [
    "bd_treaty_status",
]


def audit_corpus():
    if not MANIFEST_PATH.exists():
        print(f"FATAL: manifest.json not found: {MANIFEST_PATH}")
        sys.exit(1)

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"FATAL: invalid JSON: {exc}")
        sys.exit(1)

    instruments = manifest.get("instruments", [])

    if not isinstance(instruments, list):
        print("FATAL: 'instruments' must be a list.")
        sys.exit(1)

    errors = []
    warnings = []
    blocked_count = 0

    ids = []
    for inst in instruments:
        if isinstance(inst, dict) and inst.get("instrument_id"):
            ids.append(inst["instrument_id"])

    inst_ids = set(ids)

    print("==========================================================")
    print("MRIS CORPUS INTEGRITY AUDIT (v2.0)")
    print("==========================================================")
    print(f"MANIFEST: {MANIFEST_PATH}")
    print(f"VERSION: {manifest.get('_metadata', {}).get('version', 'UNKNOWN')}")
    print()

    # ------------------------------------------------------
    # 0. Instrument object integrity
    # ------------------------------------------------------
    for index, inst in enumerate(instruments, start=1):
        if not isinstance(inst, dict):
            errors.append(
                f"[INDEX {index}] Instrument record must be an object."
            )
            continue

        iid = inst.get("instrument_id", f"MISSING-ID-{index}")

        # --------------------------------------------------
        # 1. Required schema fields
        # --------------------------------------------------
        for field in REQUIRED_FIELDS:
            if field not in inst:
                errors.append(
                    f"[{iid}] Missing required field: {field}"
                )

        # --------------------------------------------------
        # 2. Conditional international treaty metadata
        # --------------------------------------------------
        jurisdiction = inst.get("jurisdiction")

        if jurisdiction == "INTL":
            if "bd_treaty_status" not in inst:
                errors.append(
                    f"[{iid}] Missing bd_treaty_status "
                    f"for international instrument."
                )

        # --------------------------------------------------
        # 3. Parent instrument integrity
        # --------------------------------------------------
        parent = inst.get("parent_instrument")

        if parent:
            if not isinstance(parent, str):
                errors.append(
                    f"[{iid}] parent_instrument must be a string."
                )
            elif parent not in inst_ids:
                errors.append(
                    f"[{iid}] Referential Integrity FAIL: "
                    f"parent_instrument '{parent}' does not exist."
                )

        # --------------------------------------------------
        # 4. Instrument-to-instrument implements integrity
        #
        # IMPORTANT:
        # "SOLAS Chapter IX" is NOT an instrument ID.
        # It is a provision/chapter reference and must not
        # be validated against the instrument registry.
        # --------------------------------------------------
        implements = inst.get("implements", [])

        if isinstance(implements, str):
            implements = [implements]

        if implements is None:
            implements = []

        if not isinstance(implements, list):
            errors.append(
                f"[{iid}] 'implements' must be a string or list."
            )
            implements = []

        for imp in implements:
            if not isinstance(imp, str):
                errors.append(
                    f"[{iid}] implements entry must be a string: {imp!r}"
                )
                continue

            # Only values explicitly shaped like registry IDs
            # are validated as instrument references.
            if imp.startswith(INSTRUMENT_ID_PREFIXES):
                if imp not in inst_ids:
                    errors.append(
                        f"[{iid}] Referential Integrity FAIL: "
                        f"implements instrument '{imp}' does not exist."
                    )

        # --------------------------------------------------
        # 5. Verification gate
        # --------------------------------------------------
        v_status = inst.get("verification_status")

        if v_status in {
            "REQUIRES_PRIMARY_VERIFICATION",
            "UNVERIFIED",
            "MISSING",
        }:
            blocked_count += 1
            warnings.append(
                f"[{iid}] PRODUCTION GATE BLOCKED: "
                f"{v_status} - {inst.get('short_name', '')}"
            )

        # --------------------------------------------------
        # 6. Legal conflict detection
        # --------------------------------------------------
        if (
            inst.get("bd_treaty_status")
            == "STATUS_REQUIRES_PRIMARY_VERIFICATION"
        ):
            warnings.append(
                f"[{iid}] LEGAL CONFLICT DETECTED: "
                f"treaty status requires primary verification. "
                f"Engine must return UNDETERMINED for affected "
                f"legal conclusions."
            )

        # --------------------------------------------------
        # 7. Verification metadata consistency
        # --------------------------------------------------
        if v_status == "VERIFIED_AGAINST_GAZETTE":
            if not inst.get("verification_date"):
                errors.append(
                    f"[{iid}] VERIFIED_AGAINST_GAZETTE record missing verification_date."
                )

            if not inst.get("authoritative_sources"):
                errors.append(
                    f"[{iid}] VERIFIED_AGAINST_GAZETTE record missing "
                    f"authoritative_sources."
                )

    # ------------------------------------------------------
    # 8. Duplicate IDs
    # ------------------------------------------------------
    duplicates = sorted(
        {iid for iid in ids if ids.count(iid) > 1}
    )

    if duplicates:
        for iid in duplicates:
            errors.append(
                f"[{iid}] Duplicate instrument_id."
            )

    # ------------------------------------------------------
    # Results
    # ------------------------------------------------------
    print("--- AUDIT RESULTS ---")

    if errors:
        print(f"\n[CRITICAL ERRORS]: {len(errors)}")
        for error in errors:
            print(f"  - {error}")
    else:
        print(
            "\n[PASS] Schema and Referential Integrity: 100% Valid."
        )

    if warnings:
        print(f"\n[WARNINGS / GATES]: {len(warnings)}")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("\n[WARNINGS / GATES]: 0")

    print("\n==========================================================")
    print(
        f"SUMMARY: {len(instruments)} Instruments | "
        f"{len(inst_ids)} Unique IDs | "
        f"{blocked_count} Blocked from Production"
    )
    print("==========================================================")

    if errors:
        print("\nRESULT: FAIL")
        print("Production corpus gate remains BLOCKED.")
        sys.exit(1)

    print("\nRESULT: PASS")
    print(
        "Structural corpus integrity passed. "
        "Verification blocks remain separate production gates."
    )


if __name__ == "__main__":
    audit_corpus()
