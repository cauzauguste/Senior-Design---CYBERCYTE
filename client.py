# client.py
"""
Simulated Data Ingestion Client
--------------------------------
Sends mock osquery and Zeek events to the FastAPI backend.
Useful for demonstrating live ingestion and AI-based anomaly review.
"""

import requests
import time
import json
from datetime import datetime
import random

# ==============================
# CONFIGURATION
# ==============================
API_URL = "http://127.0.0.1:8000/ingest_data"  # FastAPI endpoint
SEND_INTERVAL = 1  # seconds between sending events

# ==============================
# MOCK EVENT GENERATOR
# ==============================
def generate_mock_event(source: str) -> dict:
    """
    Generates a mock log event resembling osquery or Zeek output.
    Includes a random anomaly factor to simulate threat scoring.
    """
    timestamp = datetime.now().isoformat()
    anomaly_factor = 0.0 if random.random() < 0.8 else random.uniform(0.5, 1.0)

    if source == "osquery":
        return {
            "source": "osquery",
            "timestamp": timestamp,
            "event_type": "process_create",
            "data": (
                f"user=root, pid={int(time.time() % 1000) + 1000}, "
                f"path=/usr/bin/bash, cmdline='wget -q -O -', "
                f"anomaly_factor={anomaly_factor:.4f}"
            ),
        }

    elif source == "zeek":
        return {
            "source": "zeek",
            "timestamp": timestamp,
            "event_type": "dns_query",
            "data": (
                f"id.orig_h=10.0.0.{random.randint(2, 100)}, "
                f"id.resp_h=8.8.8.8, query=malicious-{int(time.time())}.com, "
                f"proto=udp, anomaly_factor={anomaly_factor:.4f}"
            ),
        }

    else:
        raise ValueError("Unsupported source type: must be 'osquery' or 'zeek'")

# ==============================
# SEND DATA LOOP
# ==============================
def send_events():
    """Continuously sends mock osquery + Zeek data to FastAPI backend."""
    print("\n--- Starting Demo Data Ingestion Client ---")
    print(f"Target API: {API_URL}\n")

    while True:
        try:
            events = [
                generate_mock_event("osquery"),
                generate_mock_event("zeek"),
            ]

            for event in events:
                response = requests.post(API_URL, headers={"Content-Type": "application/json"}, data=json.dumps(event))

                if response.status_code == 200:
                    result = response.json()
                    status = "🟢 OK" if result.get("is_anomaly") else "🟢 Normal"
                    print(f"[{event['source']}] Sent {event['event_type']} | Anomaly Score: {result['anomaly_score']:.2f} | {status}")
                else:
                    print(f"[{event['source']}] ❌ Failed: {response.status_code} - {response.text}")

        except requests.exceptions.ConnectionError:
            print("⚠️  Connection Error: Is the FastAPI server running on port 8000?")
            time.sleep(3)  # Wait before retrying
            continue

        except Exception as e:
            print(f"⚠️  Unexpected error: {e}")

        time.sleep(SEND_INTERVAL)

# ==============================
# MAIN ENTRY POINT
# ==============================
if __name__ == "__main__":
    send_events()
