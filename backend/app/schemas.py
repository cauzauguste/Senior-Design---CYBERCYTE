from datetime import datetime
from typing import Optional, Any, Dict, List

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
        from_attributes = True


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
        from_attributes = True


# ---------- Zeek Event schemas ----------

class ZeekEventSchema(BaseModel):
    id: int
    timestamp: datetime
    log_type: str
    source_ip: Optional[str]
    dest_ip: Optional[str]
    source_port: Optional[int]
    dest_port: Optional[int]
    protocol: Optional[str]
    event_text: Optional[str]
    severity: str
    raw_data: Dict[str, Any]
    host_id: Optional[str]
    processed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ZeekConnectionSchema(BaseModel):
    id: int
    timestamp: datetime
    uid: Optional[str]
    source_ip: str
    dest_ip: str
    source_port: int
    dest_port: int
    protocol: str
    duration: Optional[str]
    bytes_sent: int
    bytes_received: int
    connection_state: Optional[str]
    raw_data: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ZeekDNSSchema(BaseModel):
    id: int
    timestamp: datetime
    uid: Optional[str]
    source_ip: str
    dest_ip: str
    source_port: int
    dest_port: int
    query: Optional[str]
    query_type: Optional[str]
    rcode: Optional[str]
    answers: Optional[List[str]]
    raw_data: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ZeekFileSchema(BaseModel):
    id: int
    timestamp: datetime
    uid: Optional[str]
    file_id: Optional[str]
    file_name: Optional[str]
    file_size: Optional[int]
    file_mime_type: Optional[str]
    md5_hash: Optional[str]
    sha1_hash: Optional[str]
    sha256_hash: Optional[str]
    raw_data: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ZeekHTTPSchema(BaseModel):
    id: int
    timestamp: datetime
    uid: Optional[str]
    source_ip: str
    dest_ip: str
    source_port: Optional[int]
    dest_port: Optional[int]
    method: Optional[str]
    uri: Optional[str]
    referrer: Optional[str]
    user_agent: Optional[str]
    status_code: Optional[int]
    response_body_size: Optional[int]
    raw_data: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class ZeekSSLSchema(BaseModel):
    id: int
    timestamp: datetime
    uid: Optional[str]
    source_ip: str
    dest_ip: str
    source_port: Optional[int]
    dest_port: Optional[int]
    version: Optional[str]
    cipher: Optional[str]
    server_name: Optional[str]
    subject: Optional[str]
    issuer: Optional[str]
    established: Optional[bool]
    raw_data: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True
