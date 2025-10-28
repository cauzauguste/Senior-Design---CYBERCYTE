from sqlalchemy.orm import Session
from app import models

def log_threat_to_db(db: Session, event_data: dict):
    """Insert an event into the database."""
    new_event = models.Event(
        source=event_data.get("source", "unknown"),
        event_type=event_data.get("event_type", "generic"),
        severity=event_data.get("severity", "low"),
        details=event_data,
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event
