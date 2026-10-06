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
