"""
ThreatManager Loop
Continuously polls backend for new events + mitigations
and applies detection actions.
"""

import time
import requests

BACKEND = "http://127.0.0.1:8000"

def pull_events():
    """Pull recent events for monitoring."""
    try:
        r = requests.get(f"{BACKEND}/events")
        return r.json()
    except:
        return []

def pull_mitigations():
    """Pull Gemini-reviewed threats."""
    try:
        r = requests.get(f"{BACKEND}/mitigations")
        return r.json()
    except:
        return []

def run_manager_loop():
    print("▶ ThreatManager Started\n")

    while True:
        events = pull_events()
        mitigations = pull_mitigations()

        print(f"Fetched {len(events)} events; {len(mitigations)} mitigations")

        for m in mitigations:
            print(f"\n⚠ Threat {m['id']} | Confidence {m['gemini_confidence']}")
            print(f"Mitigation: {m['mitigation_suggestion']}")

        time.sleep(5)

if __name__ == "__main__":
    run_manager_loop()
