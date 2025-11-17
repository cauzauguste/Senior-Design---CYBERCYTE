# backend.py
"""
FastAPI Backend for AI Threat Detection Demo
--------------------------------------------
Handles:
- Data ingestion from osquery & Zeek clients
- Mock ML anomaly detection (Amber / Isolation Forest)
- Mock Gemini AI review for mitigation suggestions
- Storage in SQLite and retrieval for Streamlit dashboard
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import pandas as pd
import random
import json
from datetime import datetime
import os

# ==============================
# FASTAPI INITIALIZATION
# ==============================
app = FastAPI(
    title="AI Threat Detection Backend",
    description="Handles event ingestion, anomaly detection, and AI review.",
    version="1.0.0"
)

DB_FILE = "threat_events.db"

# ==============================
# DATABASE SETUP
# ==============================
def get_db_connection():
    """Create a new SQLite connection with threading disabled for FastAPI use."""
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def setup_database():
    """Create tables for events and AI-reviewed threats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS threat_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER UNIQUE,
            gemini_review TEXT,
            mitigation_suggestion TEXT,
            gemini_confidence REAL,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    conn.commit()
    conn.close()

setup_database()

# ==============================
# DATA MODELS
# ==============================
class RawEvent(BaseModel):
    source: str
    timestamp: str
    event_type: str
    data: str

class ThreatResponse(BaseModel):
    id: int
    timestamp: str
    source: str
    event_type: str
    anomaly_score: float
    is_anomaly: bool
    mitigation_suggestion: str = "N/A"
    gemini_confidence: float = 0.0

# ==============================
# MOCK AI PIPELINES
# ==============================
def ml_detection_pipeline(event: RawEvent) -> float:
    """
    Mock ML anomaly detection using an "anomaly_factor" from data string.
    In a real system, this would extract features and pass to Amber or Isolation Forest.
    """
    try:
        if "anomaly_factor=" in event.data:
            val = float(event.data.split("anomaly_factor=")[1].split(",")[0].strip())
            return val
    except Exception:
        pass
    return random.random()  # fallback if not found

def gemini_review_pipeline(event_data: str) -> dict:
    """
    Mock Gemini review that analyzes a suspicious event and returns mitigation advice.
    Replace this with an actual Gemini API call when integrating Google GenAI.
    """
    # 80% chance to flag a high-confidence threat
    if random.random() < 0.8:
        return {
            "review": (
                "High-confidence anomaly detected: Command resembles a potential malware payload "
                "download using wget or curl. Immediate action recommended."
            ),
            "mitigation": (
                "Isolate host and terminate process immediately. "
                "Check for network exfiltration or persistence scripts."
            ),
            "confidence": round(0.8 + random.random() * 0.2, 2)
        }
    else:
        return {
            "review": "Low-confidence event; activity appears within normal operating parameters.",
            "mitigation": "Monitor this host for 24 hours; no immediate action required.",
            "confidence": round(random.random() * 0.3, 2)
        }

# ==============================
# API ROUTES
# ==============================

@app.post("/ingest_data", response_model=ThreatResponse)
async def ingest_data(event: RawEvent):
    """
    Endpoint to ingest an event, run ML detection, and trigger Gemini review if needed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Run ML anomaly detection
    anomaly_score = ml_detection_pipeline(event)
    is_anomaly = 1 if anomaly_score > 0.5 else 0

    # 2. Store raw event
    cursor.execute("""
        INSERT INTO events (timestamp, source, event_type, raw_data, anomaly_score, is_anomaly)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event.timestamp, event.source, event.event_type, event.data, anomaly_score, is_anomaly))
    conn.commit()

    event_id = cursor.lastrowid

    # Default response values
    mitigation = "N/A - Below Anomaly Threshold"
    confidence = 0.0

    # 3. Run Gemini AI review for anomalies
    if is_anomaly:
        review = gemini_review_pipeline(event.data)
        cursor.execute("""
            INSERT INTO threat_detections (event_id, gemini_review, mitigation_suggestion, gemini_confidence)
            VALUES (?, ?, ?, ?)
        """, (event_id, review["review"], review["mitigation"], review["confidence"]))
        conn.commit()

        mitigation = review["mitigation"]
        confidence = review["confidence"]

    conn.close()

    # 4. Return structured response
    return ThreatResponse(
        id=event_id,
        timestamp=event.timestamp,
        source=event.source,
        event_type=event.event_type,
        anomaly_score=anomaly_score,
        is_anomaly=bool(is_anomaly),
        mitigation_suggestion=mitigation,
        gemini_confidence=confidence
    )

@app.get("/get_latest_threats")
async def get_latest_threats():
    """
    Endpoint for Streamlit dashboard to fetch latest reviewed threats.
    Joins event data with Gemini AI review results.
    """
    conn = get_db_connection()
    query = """
        SELECT
            e.id, e.timestamp, e.source, e.event_type, e.raw_data,
            e.anomaly_score, td.mitigation_suggestion, td.gemini_confidence
        FROM events e
        INNER JOIN threat_detections td ON e.id = td.event_id
        ORDER BY e.timestamp DESC
        LIMIT 100
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    return df.to_dict(orient="records")

# ==============================
# STARTUP MESSAGE
# ==============================
if __name__ == "__main__":
    print("🚀 FastAPI backend ready. Run with:")
    print("   uvicorn backend:app --host 0.0.0.0 --port 8000 --reload")
