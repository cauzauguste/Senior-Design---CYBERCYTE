from datetime import datetime
import random

# Simulated DB logger (replace later with real DB)
class LoggedEvent:
    def __init__(self, id, host_id, src_ip, event_type, event_text):
        self.id = id
        self.host_id = host_id
        self.src_ip = src_ip
        self.event_type = event_type
        self.event_text = event_text
        self.timestamp = datetime.utcnow()

def log_threat_to_db(host_id, src_ip, event_type, event_text):
    # mock DB entry with random ID
    new_id = random.randint(1000, 9999)
    return LoggedEvent(new_id, host_id, src_ip, event_type, event_text)
