"""
FastAPI Backend for CyberCyte
-----------------------------
Handles:
- Event ingestion (manual logs, osquery, Zeek)
- Mock anomaly detection
- Mock Gemini AI mitigation
- SQLite persistence
- Clean API endpoints for dashboard + manager
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import pandas as pd
import random
from datetime import datetime

# =====================================================
# FASTAPI APP
# =====================================================
app = FastAPI(
    title="CyberCyte Backend",
    description="Threat ingestion, detection, and mitigation API",
    version="1.1.0"
)

DB_FILE = "threat_events.db"

# =====================================================
# DATABASE UTILITIES
# =====================================================
def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            event_type TEXT,
            raw_data TEXT,
            anomaly_score REAL,
            is_anomaly INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS threat_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER UNIQUE,
            gemini_review TEXT,
            mitigation_suggestion TEXT,
            gemini_confidence REAL,
            FOREIGN KEY(event_id) REFERENCES events(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =====================================================
# DATA MODELS
# =====================================================
class RawEvent(BaseModel):
    timestamp: str
    source: str
    event_type: str
    data: str

class ThreatResponse(BaseModel):
    id: int
    timestamp: str
    source: str
    event_type: str
    anomaly_score: float
    is_anomaly: bool
    mitigation_suggestion: str | None = None
    gemini_confidence: float | None = None

# =====================================================
# MOCK AI LOGIC
# =====================================================
def anomaly_detection(event: RawEvent) -> float:
    """
    Simple heuristic-based anomaly score.
    Later replace with IsolationForest / LOF.
    """
    if "malicious" in event.data.lower():
        return round(random.uniform(0.7, 1.0), 2)
    return round(random.uniform(0.0, 0.4), 2)

def gemini_review(event: RawEvent) -> dict:
    return {
        "review": "Suspicious network activity detected based on traffic patterns.",
        "mitigation": "Isolate host and inspect outbound connections.",
        "confidence": round(random.uniform(0.75, 0.95), 2)
    }

# =====================================================
# INGEST EVENT
# =====================================================
@app.post("/ingest_data", response_model=ThreatResponse)
def ingest_event(event: RawEvent):
    try:
        conn = get_db()
        cur = conn.cursor()

        score = anomaly_detection(event)
        is_anomaly = 1 if score > 0.5 else 0

        cur.execute("""
            INSERT INTO events (timestamp, source, event_type, raw_data, anomaly_score, is_anomaly)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event.timestamp,
            event.source,
            event.event_type,
            event.data,
            score,
            is_anomaly
        ))

        conn.commit()
        event_id = cur.lastrowid

        mitigation = None
        confidence = None

        if is_anomaly:
            review = gemini_review(event)
            mitigation = review["mitigation"]
            confidence = review["confidence"]

            cur.execute("""
                INSERT INTO threat_detections (event_id, gemini_review, mitigation_suggestion, gemini_confidence)
                VALUES (?, ?, ?, ?)
            """, (
                event_id,
                review["review"],
                mitigation,
                confidence
            ))
            conn.commit()

        conn.close()

        return ThreatResponse(
            id=event_id,
            timestamp=event.timestamp,
            source=event.source,
            event_type=event.event_type,
            anomaly_score=score,
            is_anomaly=bool(is_anomaly),
            mitigation_suggestion=mitigation,
            gemini_confidence=confidence
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# READ EVENTS
# =====================================================
@app.get("/events")
def get_events(limit: int = 500):
    conn = get_db()
    df = pd.read_sql("""
        SELECT id, timestamp, source, event_type, raw_data, anomaly_score, is_anomaly
        FROM events
        ORDER BY timestamp DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df.to_dict(orient="records")

@app.get("/mitigations")
def get_mitigations(limit: int = 200):
    conn = get_db()
    df = pd.read_sql("""
        SELECT
            e.id,
            e.timestamp,
            e.source,
            e.event_type,
            e.raw_data,
            e.anomaly_score,
            td.mitigation_suggestion,
            td.gemini_confidence
        FROM threat_detections td
        JOIN events e ON e.id = td.event_id
        ORDER BY e.timestamp DESC
        LIMIT ?
    """, conn, params=(limit,))
    conn.close()
    return df.to_dict(orient="records")

@app.get("/get_latest_threats")
def get_latest_threats():
    return get_mitigations(100)
