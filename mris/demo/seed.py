"""Demo seed — P1 exit-criteria scenario (Part 14):

    "one real BD-flagged cargo ship fully assessed current-date"

Fictional-but-realistic vessel/crew/evidence, dated relative to today so the
assessment always exercises the full status ladder:
    * one crew CoC already expired          -> RED   (manning ladder)
    * load-line certificate expiring soon   -> YELLOW(load-line ladder)
    * safety equipment certificate expired  -> RED   (unseaworthiness ladder)
    * class certificate verified            -> GREEN
"""
from __future__ import annotations

from datetime import date, timedelta

from ..ilrmf import EvalContext

EVAL_DATE = date.today()

COMPANY = {
    "id": "co-demo-001",
    "name": "Bay Bengal Shipping Ltd.",
    "country": "BD",
    "type": "OWNER",
    "doc_issuer": "BD-DOS",
}

VESSEL = {
    "id": "v-demo-001",
    "company_id": COMPANY["id"],
    "name": "MV PADMA STAR",
    "imo_number": "9521457",
    "flag": "BD",
    "gross_tonnage": 24500.0,
    "net_tonnage": 13100.0,
    "deadweight": 38200.0,
    "ship_type": "CARGO",
    "keel_laid_date": "2010-03-15",
    "build_date": "2011-06-01",
    "class_society": "BKI",
    "ism_doc_no": "BD-ISM-DOC-2019-0442",
    "smc_no": "BD-SMC-2022-0442",
}

CREW = [
    {
        "id": "sf-001", "full_name": "A. Rahman", "rank": "MASTER",
        "certificates": [
            {"type": "COC", "cert_no": "BD-COC-M-8812", "issuer": "BD-DOS",
             "issue_date": str(EVAL_DATE - timedelta(days=365 * 4)),
             "expiry_date": str(EVAL_DATE - timedelta(days=10)),      # EXPIRED
             "verification_status": "VERIFIED"},
        ],
        "rest_hours": {"compliant": True},
    },
    {
        "id": "sf-002", "full_name": "S. Karim", "rank": "CHIEF_OFFICER",
        "certificates": [
            {"type": "COC", "cert_no": "BD-COC-CO-4471", "issuer": "BD-DOS",
             "issue_date": str(EVAL_DATE - timedelta(days=365 * 2)),
             "expiry_date": str(EVAL_DATE + timedelta(days=45)),      # expiring
             "verification_status": "VERIFIED"},
        ],
        "rest_hours": {"compliant": True},
    },
    {
        "id": "sf-003", "full_name": "M. Islam", "rank": "AB",
        "certificates": [
            {"type": "COC", "cert_no": "BD-COC-AB-9903", "issuer": "BD-DOS",
             "issue_date": str(EVAL_DATE - timedelta(days=365)),
             "expiry_date": str(EVAL_DATE + timedelta(days=365 * 2)),
             "verification_status": "VERIFIED"},
        ],
        "rest_hours": {"compliant": True},
    },
    {
        "id": "sf-004", "full_name": "R. Das", "rank": "OILER",
        "certificates": [
            {"type": "COP", "cert_no": "BD-COP-OL-5510", "issuer": "BD-DOS",
             "issue_date": str(EVAL_DATE - timedelta(days=365)),
             "expiry_date": str(EVAL_DATE + timedelta(days=365 * 3)),
             "verification_status": "VERIFIED"},
        ],
        "rest_hours": {"compliant": False},
    },
]

EVIDENCE = [
    {"id": "ev-001", "evidence_type": "SAFE_MANNING_DOCUMENT",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-SMD-2024-118", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=365)),
     "expiry_date": str(EVAL_DATE + timedelta(days=365 * 2)),
     "verification_status": "VERIFIED"},
    {"id": "ev-002", "evidence_type": "LOAD_LINE_CERTIFICATE",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-LL-2021-77", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=365 * 3)),
     "expiry_date": str(EVAL_DATE + timedelta(days=45)),              # YELLOW
     "verification_status": "VERIFIED"},
    {"id": "ev-003", "evidence_type": "CLASS_CERTIFICATE",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BKI-CLASS-2023-331", "issuer": "BKI",
     "issue_date": str(EVAL_DATE - timedelta(days=300)),
     "expiry_date": str(EVAL_DATE + timedelta(days=365 * 2)),
     "verification_status": "VERIFIED"},
    {"id": "ev-004", "evidence_type": "SAFETY_EQUIPMENT_CERTIFICATE",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-SE-2019-204", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=365 * 5)),
     "expiry_date": str(EVAL_DATE - timedelta(days=20)),             # EXPIRED -> RED
     "verification_status": "VERIFIED"},
    {"id": "ev-005", "evidence_type": "LICENSE_TO_SAIL",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-LS-2021-019", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=365 * 3)),
     "expiry_date": str(EVAL_DATE - timedelta(days=5)),              # EXPIRED -> RED (S66)
     "verification_status": "VERIFIED"},
    # --- MARPOL evidence (Annexes I / V / VI) ---
    {"id": "ev-006", "evidence_type": "OIL_RECORD_BOOK",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-ORB-2024-018", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=300)),
     "expiry_date": str(EVAL_DATE + timedelta(days=900)),
     "verification_status": "VERIFIED"},
    {"id": "ev-007", "evidence_type": "GARBAGE_MANAGEMENT_PLAN",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-GMP-2023-077", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=500)),
     "expiry_date": None,
     "verification_status": "VERIFIED"},
    {"id": "ev-008", "evidence_type": "GARBAGE_RECORD_BOOK",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-GRB-2024-018", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=300)),
     "expiry_date": str(EVAL_DATE + timedelta(days=900)),
     "verification_status": "VERIFIED"},
    {"id": "ev-009", "evidence_type": "IAPP_CERTIFICATE",
     "entity_type": "VESSEL", "entity_id": VESSEL["id"],
     "certificate_no": "BD-IAPP-2019-114", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - timedelta(days=365 * 5)),
     "expiry_date": str(EVAL_DATE - timedelta(days=15)),             # EXPIRED -> RED (Annex VI)
     "verification_status": "VERIFIED"},
]

REQUIRED_RANKS = ["MASTER", "CHIEF_OFFICER", "AB", "OILER"]

VOYAGE = {
    "id": "vy-001",
    "port_from": "DACCA",
    "port_to": "CHITTAGONG",
    "phase": "PRE_VOYAGE",
    "legs": [
        {"seq": 1, "zone_type": "INTERNAL_WATERS", "coastal_state": "BD"},
        {"seq": 2, "zone_type": "TERRITORIAL", "coastal_state": "BD"},
    ],
}


def build_context() -> EvalContext:
    return EvalContext(
        eval_date=EVAL_DATE,
        facts={
            "company": COMPANY,
            "vessel": VESSEL,
            "required_ranks": REQUIRED_RANKS,
            "min_safe_manning": 4,
        },
        crew=CREW,
        evidence=EVIDENCE,
        certificates=[],
        voyage=VOYAGE,
    )


APPLICABILITY_FACTS = {
    "flag": "BD",
    "operation": "SEA_VOYAGE",
    "ship_type": "CARGO",
    "zone_type": "TERRITORIAL",
    "coastal_state": "BD",
    "port": "CHITTAGONG",
}
