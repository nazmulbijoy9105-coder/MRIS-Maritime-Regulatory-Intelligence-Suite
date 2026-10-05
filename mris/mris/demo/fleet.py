"""Demo fleet — three BD-flagged vessels exercising the full status spectrum.

Fictional-but-realistic demo data; every status below is computed by the real
engine from real rule specs (nothing hard-coded):
    MV PADMA STAR     -> RED    (expired Master CoC + expired safety cert)
    MV MEGHNA TRADER  -> GREEN  (all obligations satisfied)
    MV KARNAPHULI     -> YELLOW (certificates expiring within 60 days)
"""
from __future__ import annotations

from datetime import date, timedelta

from ..ilrmf import EvalContext

EVAL_DATE = date.today()
D = timedelta


def _certs(*specs) -> list[dict]:
    out = []
    for cert_type, issue_off, expiry_off, status in specs:
        out.append({
            "type": cert_type,
            "issue_date": str(EVAL_DATE + D(days=issue_off)),
            "expiry_date": str(EVAL_DATE + D(days=expiry_off)),
            "verification_status": status,
        })
    return out


# ---------------------------------------------------------------------------
# Vessel 2 — clean vessel, GREEN
# ---------------------------------------------------------------------------

COMPANY_GREEN = {"id": "co-demo-002", "name": "Meghna Marine Ltd.", "country": "BD",
                 "type": "OWNER", "doc_issuer": "BD-DOS"}

VESSEL_GREEN = {
    "id": "v-demo-002", "company_id": COMPANY_GREEN["id"],
    "name": "MV MEGHNA TRADER", "imo_number": "9612345", "flag": "BD",
    "gross_tonnage": 31200.0, "net_tonnage": 16800.0, "deadweight": 52100.0,
    "ship_type": "TANKER", "keel_laid_date": "2015-04-20", "build_date": "2016-08-11",
    "class_society": "BKI", "ism_doc_no": "BD-ISM-DOC-2021-0871", "smc_no": "BD-SMC-2024-0871",
}

CREW_GREEN = [
    {"id": "sf-101", "full_name": "H. Chowdhury", "rank": "MASTER",
     "certificates": _certs(("COC", -365 * 3, 365 * 2, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-102", "full_name": "T. Ahmed", "rank": "CHIEF_OFFICER",
     "certificates": _certs(("COC", -365 * 2, 365 * 3, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-103", "full_name": "J. Uddin", "rank": "AB",
     "certificates": _certs(("COC", -365, 365 * 4, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-104", "full_name": "K. Roy", "rank": "OILER",
     "certificates": _certs(("COP", -365, 365 * 4, "VERIFIED")),
     "rest_hours": {"compliant": True}},
]

EVIDENCE_GREEN = [
    {"id": "ev-101", "evidence_type": "SAFE_MANNING_DOCUMENT", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-SMD-2025-042", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=200)), "expiry_date": str(EVAL_DATE + D(days=1200)),
     "verification_status": "VERIFIED"},
    {"id": "ev-102", "evidence_type": "LOAD_LINE_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-LL-2024-118", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=300)), "expiry_date": str(EVAL_DATE + D(days=900)),
     "verification_status": "VERIFIED"},
    {"id": "ev-103", "evidence_type": "CLASS_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BKI-CLASS-2025-090", "issuer": "BKI",
     "issue_date": str(EVAL_DATE - D(days=150)), "expiry_date": str(EVAL_DATE + D(days=1100)),
     "verification_status": "VERIFIED"},
    {"id": "ev-104", "evidence_type": "SAFETY_EQUIPMENT_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-SE-2024-551", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=250)), "expiry_date": str(EVAL_DATE + D(days=1000)),
     "verification_status": "VERIFIED"},
    {"id": "ev-105", "evidence_type": "LICENSE_TO_SAIL", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-LS-2025-077", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=120)), "expiry_date": str(EVAL_DATE + D(days=1100)),
     "verification_status": "VERIFIED"},
    # --- MARPOL (all valid → GREEN) ---
    {"id": "ev-106", "evidence_type": "OIL_RECORD_BOOK", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-ORB-2025-088", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=140)), "expiry_date": str(EVAL_DATE + D(days=1200)),
     "verification_status": "VERIFIED"},
    {"id": "ev-107", "evidence_type": "GARBAGE_MANAGEMENT_PLAN", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-GMP-2025-044", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=140)), "expiry_date": None,
     "verification_status": "VERIFIED"},
    {"id": "ev-108", "evidence_type": "GARBAGE_RECORD_BOOK", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-GRB-2025-088", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=140)), "expiry_date": str(EVAL_DATE + D(days=1200)),
     "verification_status": "VERIFIED"},
    {"id": "ev-109", "evidence_type": "IAPP_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_GREEN["id"], "certificate_no": "BD-IAPP-2025-021", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=140)), "expiry_date": str(EVAL_DATE + D(days=1200)),
     "verification_status": "VERIFIED"},
]

# ---------------------------------------------------------------------------
# Vessel 3 — expiring certificates, YELLOW
# ---------------------------------------------------------------------------

COMPANY_YELLOW = {"id": "co-demo-003", "name": "Karnaphuli Carriers Ltd.", "country": "BD",
                  "type": "OWNER", "doc_issuer": "BD-DOS"}

VESSEL_YELLOW = {
    "id": "v-demo-003", "company_id": COMPANY_YELLOW["id"],
    "name": "MV KARNAPHULI", "imo_number": "9445678", "flag": "BD",
    "gross_tonnage": 18900.0, "net_tonnage": 10200.0, "deadweight": 28400.0,
    "ship_type": "CARGO", "keel_laid_date": "2008-09-30", "build_date": "2009-12-15",
    "class_society": "BKI", "ism_doc_no": "BD-ISM-DOC-2020-0219", "smc_no": "BD-SMC-2023-0219",
}

CREW_YELLOW = [
    {"id": "sf-201", "full_name": "S. Hossain", "rank": "MASTER",
     "certificates": _certs(("COC", -365 * 4, 50, "VERIFIED")),   # expires in 50 days
     "rest_hours": {"compliant": True}},
    {"id": "sf-202", "full_name": "A. Kabir", "rank": "CHIEF_OFFICER",
     "certificates": _certs(("COC", -365 * 2, 365 * 2, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-203", "full_name": "M. Sarker", "rank": "AB",
     "certificates": _certs(("COC", -365, 365 * 3, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-204", "full_name": "R. Barua", "rank": "OILER",
     "certificates": _certs(("COP", -365, 365 * 3, "VERIFIED")),
     "rest_hours": {"compliant": True}},
]

EVIDENCE_YELLOW = [
    {"id": "ev-201", "evidence_type": "SAFE_MANNING_DOCUMENT", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-SMD-2023-201", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=400)), "expiry_date": str(EVAL_DATE + D(days=55)),
     "verification_status": "VERIFIED"},                                  # expiring
    {"id": "ev-202", "evidence_type": "LOAD_LINE_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-LL-2021-330", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=1000)), "expiry_date": str(EVAL_DATE + D(days=30)),
     "verification_status": "VERIFIED"},                                  # expiring
    {"id": "ev-203", "evidence_type": "CLASS_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BKI-CLASS-2024-140", "issuer": "BKI",
     "issue_date": str(EVAL_DATE - D(days=350)), "expiry_date": str(EVAL_DATE + D(days=800)),
     "verification_status": "VERIFIED"},
    {"id": "ev-204", "evidence_type": "SAFETY_EQUIPMENT_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-SE-2022-771", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=800)), "expiry_date": str(EVAL_DATE + D(days=700)),
     "verification_status": "VERIFIED"},
    {"id": "ev-205", "evidence_type": "LICENSE_TO_SAIL", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-LS-2024-310", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=300)), "expiry_date": str(EVAL_DATE + D(days=640)),
     "verification_status": "VERIFIED"},
    # --- MARPOL (garbage record book expiring → YELLOW) ---
    {"id": "ev-206", "evidence_type": "OIL_RECORD_BOOK", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-ORB-2024-219", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=350)), "expiry_date": str(EVAL_DATE + D(days=700)),
     "verification_status": "VERIFIED"},
    {"id": "ev-207", "evidence_type": "GARBAGE_MANAGEMENT_PLAN", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-GMP-2023-188", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=600)), "expiry_date": None,
     "verification_status": "VERIFIED"},
    {"id": "ev-208", "evidence_type": "GARBAGE_RECORD_BOOK", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-GRB-2023-219", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=600)), "expiry_date": str(EVAL_DATE + D(days=40)),
     "verification_status": "VERIFIED"},
    {"id": "ev-209", "evidence_type": "IAPP_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_YELLOW["id"], "certificate_no": "BD-IAPP-2022-451", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=800)), "expiry_date": str(EVAL_DATE + D(days=700)),
     "verification_status": "VERIFIED"},
]


# ---------------------------------------------------------------------------
# Vessel 4 — missing mandatory documents, BLACK (human review)
# ---------------------------------------------------------------------------

COMPANY_BLACK = {"id": "co-demo-004", "name": "Shitalakkhya Shipping Ltd.", "country": "BD",
                 "type": "OWNER", "doc_issuer": "BD-DOS"}

VESSEL_BLACK = {
    "id": "v-demo-004", "company_id": COMPANY_BLACK["id"],
    "name": "MV SHITALAKSHYA", "imo_number": "9337890", "flag": "BD",
    "gross_tonnage": 12800.0, "net_tonnage": 6900.0, "deadweight": 19500.0,
    "ship_type": "CARGO", "keel_laid_date": "2006-02-12", "build_date": "2007-05-30",
    "class_society": "BKI", "ism_doc_no": "BD-ISM-DOC-2019-0603", "smc_no": "BD-SMC-2022-0603",
}

CREW_BLACK = [
    {"id": "sf-301", "full_name": "N. Islam", "rank": "MASTER",
     "certificates": _certs(("COC", -365 * 2, 365 * 3, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-302", "full_name": "F. Ahmed", "rank": "CHIEF_OFFICER",
     "certificates": _certs(("COC", -365, 365 * 4, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-303", "full_name": "P. Das", "rank": "AB",
     "certificates": _certs(("COC", -365, 365 * 4, "VERIFIED")),
     "rest_hours": {"compliant": True}},
    {"id": "sf-304", "full_name": "L. Miah", "rank": "OILER",
     "certificates": _certs(("COP", -365, 365 * 4, "VERIFIED")),
     "rest_hours": {"compliant": True}},
]

EVIDENCE_BLACK = [
    # SAFE_MANNING_DOCUMENT deliberately absent  -> S082 BLACK (lawyer review)
    {"id": "ev-301", "evidence_type": "LOAD_LINE_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-LL-2023-450", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=400)), "expiry_date": str(EVAL_DATE + D(days=1100)),
     "verification_status": "VERIFIED"},
    {"id": "ev-302", "evidence_type": "CLASS_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BKI-CLASS-2024-205", "issuer": "BKI",
     "issue_date": str(EVAL_DATE - D(days=200)), "expiry_date": str(EVAL_DATE + D(days=900)),
     "verification_status": "VERIFIED"},
    {"id": "ev-303", "evidence_type": "SAFETY_EQUIPMENT_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-SE-2023-620", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=350)), "expiry_date": str(EVAL_DATE + D(days=850)),
     "verification_status": "VERIFIED"},
    {"id": "ev-304", "evidence_type": "LICENSE_TO_SAIL", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-LS-2024-412", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=180)), "expiry_date": str(EVAL_DATE + D(days=760)),
     "verification_status": "VERIFIED"},
    # OIL_RECORD_BOOK deliberately absent -> MARPOL Annex I BLACK (lawyer review)
    {"id": "ev-305", "evidence_type": "GARBAGE_MANAGEMENT_PLAN", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-GMP-2024-301", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=220)), "expiry_date": None,
     "verification_status": "VERIFIED"},
    {"id": "ev-306", "evidence_type": "GARBAGE_RECORD_BOOK", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-GRB-2024-301", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=220)), "expiry_date": str(EVAL_DATE + D(days=1000)),
     "verification_status": "VERIFIED"},
    {"id": "ev-307", "evidence_type": "IAPP_CERTIFICATE", "entity_type": "VESSEL",
     "entity_id": VESSEL_BLACK["id"], "certificate_no": "BD-IAPP-2023-620", "issuer": "BD-DOS",
     "issue_date": str(EVAL_DATE - D(days=300)), "expiry_date": str(EVAL_DATE + D(days=1100)),
     "verification_status": "VERIFIED"},
]


def build_context(vessel: dict, crew: list[dict], evidence: list[dict],
                  company: dict) -> EvalContext:
    return EvalContext(
        eval_date=EVAL_DATE,
        facts={"company": company, "vessel": vessel,
               "required_ranks": ["MASTER", "CHIEF_OFFICER", "AB", "OILER"],
               "min_safe_manning": 4},
        crew=crew, evidence=evidence,
        voyage={"id": f"vy-{vessel['id']}", "phase": "PRE_VOYAGE", "legs": [
            {"seq": 1, "zone_type": "INTERNAL_WATERS", "coastal_state": "BD"},
            {"seq": 2, "zone_type": "TERRITORIAL", "coastal_state": "BD"},
        ]},
    )


FLEET = [
    {"company": {"id": "co-demo-001", "name": "Bay Bengal Shipping Ltd.", "country": "BD",
                 "type": "OWNER", "doc_issuer": "BD-DOS"},
     # MV PADMA STAR lives in .seed for the P1 demo; imported lazily to avoid cycles
     "seed_module": "padma"},
    {"company": COMPANY_GREEN, "vessel": VESSEL_GREEN, "crew": CREW_GREEN,
     "evidence": EVIDENCE_GREEN},
    {"company": COMPANY_YELLOW, "vessel": VESSEL_YELLOW, "crew": CREW_YELLOW,
     "evidence": EVIDENCE_YELLOW},
    {"company": COMPANY_BLACK, "vessel": VESSEL_BLACK, "crew": CREW_BLACK,
     "evidence": EVIDENCE_BLACK},
]
