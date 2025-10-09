from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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
