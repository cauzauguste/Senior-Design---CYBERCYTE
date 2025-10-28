#schemas.py 
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    class Config:
        orm_mode = True

class ClientAppCreate(BaseModel):
    name: str

class EventCreate(BaseModel):
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    severity: Optional[str] = "medium"
    description: Optional[str] = None

class MonitoringCreate(BaseModel):
    metric_name: str
    metric_value: str

class GenerateEventRequest(BaseModel):
    timestamp: Optional[datetime] = None
    host_id: str
    src_ip: str = ''
    dst_ip: str = ''
    event_type: str
    event_text: str
    bytes_sent: int = 0
    bytes_received: int = 0

class MitigationRequest(BaseModel):
    event_id: int
    manual_override: bool = False
