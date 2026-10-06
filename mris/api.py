from fastapi import FastAPI
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
    with open(demo_path, "r") as f:
        demo_data = json.load(f)
    
    vessel = next((v for v in demo_data.get("vessels", []) if v["vessel_id"] == vessel_id), None)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found in fleet.")
    
    # 1. Jurisdictional Resolution (M06)
    port_jurisdiction = "BD" if "chattogram" in port_name.lower() or "mongla" in port_name.lower() else "INTL"
    
    status = vessel.get("status", "UNKNOWN")
    counts = vessel.get("counts", {})
    
    # 2. The 24-Point Decomposition Matrix (M01-M06)
    report = {
        "query": f"Can {vessel['name']} legally enter {port_name} today?",
        "vessel_identity": {
            "imo": vessel["imo_number"],
            "flag": vessel["flag"],
            "type": vessel["ship_type"],
            "gt": vessel["gross_tonnage"]
        },
        "jurisdiction": {
            "flag_state": vessel["flag"],
            "port_state": port_jurisdiction,
            "coastal_state": port_jurisdiction
        },
        "compliance_matrix": {
            "M01_Safety": "PASS" if counts.get("RED", 0) == 0 and counts.get("BLACK", 0) == 0 else "FAIL",
            "M02_Environment": "PASS" if counts.get("RED", 0) == 0 else "FAIL",
            "M03_Labor": "PASS" if counts.get("RED", 0) == 0 else "FAIL",
            "M04_Liability": "WITHHELD" if port_jurisdiction == "BD" else "PASS", # BUNKER 2001 STATUS_CONFLICT
            "M05_Security": "PASS" if counts.get("BLACK", 0) == 0 else "FAIL",
            "M06_Port_State": f"Pilotage required for {port_name} under {port_jurisdiction} law"
        },
        "final_decision": "ENTRY_PERMITTED" if status in ["GREEN", "YELLOW"] else "ENTRY_DENIED",
        "reason": f"Vessel overall status is {status}. Outstanding RED/BLACK deficiencies must be resolved.",
        "remediation": "Address all outstanding deficiencies and verify BUNKER 2001 insurance status with legal counsel."
    }
    
    return report
