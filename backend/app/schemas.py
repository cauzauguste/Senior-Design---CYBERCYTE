from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel


# ---------- Raw log schemas ----------

class RawLogResponse(BaseModel):
    id: int
    host_id: str
    src_ip: str
    dst_ip: Optional[str]
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


# ---------- Event schemas ----------

class EventBase(BaseModel):
    source: str
    event_type: str
    severity: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class EventCreate(EventBase):
    pass


class Event(EventBase):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True
