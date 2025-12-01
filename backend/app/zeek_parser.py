# app/zeek_parser.py
from app.threat_manager import log_threat_to_db

def get_zeek_events():
    # Simulate Zeek events (replace with real Zeek parsing)
    events = [
        {
            "host_id": "zeek-host1",
            "src_ip": "192.168.1.50",
            "event_type": "scan",
            "event_text": "Zeek detected potential port scan"
        },
        {
            "host_id": "zeek-host2",
            "src_ip": "192.168.1.51",
            "event_type": "malware",
            "event_text": "Zeek detected suspicious malware pattern"
        }
    ]
    return events

def push_zeek_events_to_db():
    for event in get_zeek_events():
        log_threat_to_db(
            host_id=event["host_id"],
            src_ip=event["src_ip"],
            event_type=event["event_type"],
            event_text=event["event_text"]
        )
