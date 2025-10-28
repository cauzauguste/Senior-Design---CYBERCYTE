import json
import random

def get_osquery_events():
    """Mock or integrate with real osquery to collect system events."""
    # Example simulated data
    return [
        {
            "source": "osquery",
            "event_type": "process_start",
            "severity": random.choice(["low", "medium", "high"]),
            "details": {"process": "nginx", "pid": 1234},
        }
    ]
