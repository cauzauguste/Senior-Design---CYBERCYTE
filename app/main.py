# app/main.py
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.threat_manager import ThreatManager
from app.db_adapter import DBAdapter
from typing import List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# Choose backend: "supabase" or "sqlalchemy"
DB_BACKEND = "supabase"  # change to "sqlalchemy" if needed
db_adapter = DBAdapter(backend=DB_BACKEND)

app = FastAPI(title="CYBERCYTE Threat Manager API")

# CORS (optional, for Streamlit frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# -------------------------
# Pydantic models
# -------------------------
class RawLogResponse(BaseModel):
    host_id: str
    src_ip: str
    dst_ip: str
    event_type: str
    event_text: str
    bytes_sent: int
    bytes_received: int
    timestamp: datetime
    processed: int

    class Config:
        orm_mode = True

class GenerateEventRequest(BaseModel):
    host_id: str
    src_ip: str
    event_type: str
    event_text: str

# -------------------------
# ThreatManager background
# -------------------------
threat_manager = ThreatManager(db_backend=DB_BACKEND)

@app.on_event("startup")
async def start_background_loop():
    asyncio.create_task(threat_manager.run_loop(interval_seconds=10))
    print("ThreatManager loop started...")

@app.on_event("shutdown")
def stop_background_loop():
    threat_manager.stop()
    print("ThreatManager loop stopped.")

# -------------------------
# API Endpoints
# -------------------------
@app.get("/raw_logs", response_model=List[RawLogResponse])
def get_raw_logs(limit: int = 50):
    if DB_BACKEND == "supabase":
        res = db_adapter.db_adapter.insert_raw_log({"dummy": 0})  # dummy to access supabase client
        try:
            data = db_adapter.db_adapter.supabase.table("raw_logs").select("*").limit(limit).execute().data
            return data
        except Exception as e:
            print("Supabase fetch error:", e)
            return []
    else:
        # SQLAlchemy
        db = db_adapter.db_adapter.SessionLocal()
        try:
            data = db.query(db_adapter.db_adapter.RawLog).order_by(db_adapter.db_adapter.RawLog.timestamp.desc()).limit(limit).all()
            return data
        finally:
            db.close()

@app.post("/generate_event")
def generate_event(event: GenerateEventRequest):
    logged_event = db_adapter.insert_raw_log({
        "host_id": event.host_id,
        "src_ip": event.src_ip,
        "dst_ip": "",
        "event_type": event.event_type,
        "event_text": event.event_text,
        "bytes_sent": 0,
        "bytes_received": 0,
        "timestamp": datetime.utcnow(),
        "processed": 1
    })
    return {"status": "ok", "event": logged_event}
