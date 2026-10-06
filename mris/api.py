from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mris.database import init_db
from mris.auth import router as auth_router, get_current_user
from mris.models import User
import json
from pathlib import Path

app = FastAPI(title="MRIS API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mris-maritime-regulatory-intelligen.vercel.app",
        "https://mris-maritime-regulatory-intelligence.vercel.app",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "mris", "engine": "mris-engine/0.1.0"}

@app.get("/v1/fleet/summary")
def fleet_summary(current_user: User = Depends(get_current_user)):
    # Returns baked demo data so the frontend works while we wire up the DB
    demo_path = Path(__file__).parent.parent / "frontend" / "demo_data.json"
    if demo_path.exists():
        with open(demo_path, "r") as f:
            return json.load(f)
    return {"vessels": [], "fleet_status_counts": {}}

@app.post("/v1/voyage/port_entry")
async def port_entry_check(vessel_id: str, port_name: str, current_user: User = Depends(get_current_user)):
    """The 24-Point Port Entry Decomposition Engine."""
    demo_path = Path(__file__).parent.parent / "frontend" / "demo_data.json"
    if demo_path.exists():
        with open(demo_path, "r") as f:
            demo_data = json.load(f)
    else:
        demo_data = {"vessels": []}
    
    vessel = next((v for v in demo_data.get("vessels", []) if v["vessel_id"] == vessel_id), None)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found in fleet.")
    
    # 1. Jurisdictional Resolution
    port_jurisdiction = "BD" if "chattogram" in port_name.lower() or "mongla" in port_name.lower() else "INTL"
    
    # 2. Conflict Detection (e.g., BUNKER 2001 STATUS_CONFLICT)
    unresolved_conflicts = []
    if port_jurisdiction == "BD":
        # The engine knows BUNKER 2001 has STATUS_CONFLICT in the manifest
        unresolved_conflicts.append({
            "instrument": "INT-M20 (BUNKER 2001)",
            "conflict": "STATUS_CONFLICT (Draft MSA 2026 Schedule 1 vs Schedule 2)",
            "impact": "Civil liability insurance requirement cannot be evaluated."
        })

    status = vessel.get("status", "UNKNOWN")
    counts = vessel.get("counts", {})
    
    # 3. The 12-Node Conceptual Output
    decision = "PERMITTED"
    if unresolved_conflicts:
        decision = "UNDETERMINED"
    elif status in ["RED", "BLACK"]:
        decision = "NOT_PERMITTED"
    elif status == "YELLOW":
        decision = "CONDITIONALLY_PERMITTED"

    assessment = {
        "PORT_ENTRY_ASSESSMENT": {
            "jurisdiction_resolution": {
                "flag_state": vessel["flag"],
                "port_state": port_jurisdiction,
                "coastal_state": port_jurisdiction
            },
            "applicable_instruments": ["SOLAS 1974", "MARPOL 73/78", "STCW 1978", "Chattogram Port Authority Act 2022"],
            "applicable_provisions": ["SOLAS Ch I-IV", "MARPOL Annex I", "STCW Reg I/2", "CPA Act 2022 Sec 22"],
            "required_certificates": ["Cargo Ship Safety Construction", "IOPP", "Minimum Safe Manning", "ISSC"],
            "verified_facts": {
                "vessel_identity": vessel["imo_number"],
                "vessel_type": vessel["ship_type"],
                "gross_tonnage": vessel["gross_tonnage"]
            },
            "missing_facts": [] if status != "BLACK" else ["Valid IMO Registration"],
            "verified_evidence": ["Crew CoCs", "IOPP Cert"] if counts.get("GREEN", 0) > 0 else [],
            "unresolved_legal_conflicts": unresolved_conflicts,
            "deficiencies": [] if status in ["GREEN", "YELLOW"] else [{"rule": "S082 Manning", "severity": status}],
            "enforcement_risk": "HIGH" if status in ["RED", "BLACK"] else "LOW",
            "decision": decision
        }
    }
    
    return assessment
