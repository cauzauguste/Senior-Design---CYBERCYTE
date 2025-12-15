# client.py
"""
Zeek Log Ingestion Client
-------------------------
Parses Zeek logs (conn, files, http, packet_filter)
and sends events to the FastAPI backend.
"""

import requests
import csv
from datetime import datetime

API_URL = "http://127.0.0.1:8000/ingest_data"

# ======================================================
# Helper: Convert Zeek epoch timestamp to ISO format
# ======================================================
def zeek_ts_to_iso(ts):
    return datetime.utcfromtimestamp(float(ts)).isoformat()

# ======================================================
# Generic Zeek Log Parser
# ======================================================
def parse_zeek_log(filepath, event_type):
    events = []

    with open(filepath, "r") as f:
        reader = csv.reader(f, delimiter="\t")
        headers = None

        for row in reader:
            if not row or row[0].startswith("#"):
                # Capture headers
                if row and row[0] == "#fields":
                    headers = row[1:]
                continue

            if headers is None:
                continue

            record = dict(zip(headers, row))

            event = {
                "source": "zeek",
                "timestamp": zeek_ts_to_iso(record["ts"]),
                "event_type": event_type,
                "data": ", ".join(f"{k}={v}" for k, v in record.items())
            }

            events.append(event)

    return events

# ======================================================
# Send Events to Backend
# ======================================================
def send_events(events):
    for event in events:
        try:
            r = requests.post(API_URL, json=event, timeout=5)
            r.raise_for_status()
            print(f"✔ Sent {event['event_type']} at {event['timestamp']}")
        except Exception as e:
            print(f"✖ Failed to send event: {e}")

# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    print("📡 Sending Zeek Logs to Backend...\n")

    all_events = []

    all_events += parse_zeek_log("Conn.log", "connection")
    all_events += parse_zeek_log("Files.log", "file_activity")
    all_events += parse_zeek_log("Http.log", "http_request")
    all_events += parse_zeek_log("Packet_filter.log", "packet_filter")

    send_events(all_events)

    print(f"\n✅ Finished sending {len(all_events)} events.")
