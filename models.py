from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel
import datetime

Base = declarative_base()

# ZEEK NETWORK LOGS TABLE
# ============================================================
class ZeekNetworkLog(Base):
    __tablename__ = "zeek_network_logs"

    uid = Column(String, primary_key=True, index=True)  # Unique identifier
    ts = Column(DateTime, default=datetime.datetime.utcnow)  # Timestamp
    id_orig_h = Column(String)  # Internal client (source)
    id_resp_h = Column(String)  # External server (destination)
    service = Column(String)  # Protocol (http, ssl)
    http_host = Column(String)  # Domain requested
    conn_state = Column(String)  # Connection status (e.g., RSTR)
    dns_query = Column(String)  # DNS lookup
    ja3_fingerprint = Column(String)  # Malware fingerprint

    # Relationships
    osquery_events = relationship("OsqueryEndpointEvent", back_populates="zeek_event")
    alerts = relationship("LiveAlert", back_populates="zeek_source")


# OSQUERY ENDPOINT EVENTS TABLE
# ============================================================
class OsqueryEndpointEvent(Base):
    __tablename__ = "osquery_endpoint_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    host_identifier = Column(String)  # Which VM generated the data
    process_name = Column(String)
    pid = Column(Integer)
    parent_pid = Column(Integer)
    cmdline = Column(String)
    remote_ip = Column(String, ForeignKey("zeek_network_logs.id_resp_h"))  # Bridge to Zeek
    path = Column(String)
    username = Column(String)

    zeek_event = relationship("ZeekNetworkLog", back_populates="osquery_events")
    alerts = relationship("LiveAlert", back_populates="osquery_source")


# LIVE ALERT TABLE 
# ============================================================
class LiveAlert(Base):
    __tablename__ = "live_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    alert_type = Column(String)  # e.g., "C2 Beaconing"
    infected_host = Column(String, ForeignKey("osquery_endpoint_events.host_identifier"))
    remote_ip = Column(String, ForeignKey("zeek_network_logs.id_resp_h"))
    action_status = Column(String, default="Review")  # Review, Blocked, Escalated, etc.

    # Relationships
    zeek_source = relationship("ZeekNetworkLog", back_populates="alerts")
    osquery_source = relationship("OsqueryEndpointEvent", back_populates="alerts")


# PYDANTIC MODELS (for API/Dashboard Integration)
# ============================================================
class ZeekNetworkLogSchema(BaseModel):
    uid: str
    ts: datetime.datetime
    id_orig_h: str
    id_resp_h: str
    service: str
    http_host: str
    conn_state: str
    dns_query: str
    ja3_fingerprint: str

    class Config:
        orm_mode = True


class OsqueryEndpointEventSchema(BaseModel):
    id: int
    timestamp: datetime.datetime
    host_identifier: str
    process_name: str
    pid: int
    parent_pid: int
    cmdline: str
    remote_ip: str
    path: str
    username: str

    class Config:
        orm_mode = True


class LiveAlertSchema(BaseModel):
    id: int
    timestamp: datetime.datetime
    alert_type: str
    infected_host: str
    remote_ip: str
    action_status: str

    class Config:
        orm_mode = True
