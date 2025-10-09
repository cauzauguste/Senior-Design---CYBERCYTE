<<<<<<< HEAD
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from .database import Base
=======
# models.py
from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
<<<<<<< HEAD
    timestamp = Column(DateTime, default=datetime.utcnow)
    name = Column(String, index=True)
    severity = Column(String, default="medium")
    details = Column(JSON, nullable=True)
    mitigated = Column(Integer, default=0)


class RawLog(Base):
    __tablename__ = "raw_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    host_id = Column(String)
    src_ip = Column(String)
    dst_ip = Column(String)
    event_type = Column(String)
    event_text = Column(String)
    bytes_sent = Column(Integer, default=0)
    bytes_received = Column(Integer, default=0)
    processed = Column(Integer, default=0)
=======
    src_ip = Column(String, index=True)
    dst_ip = Column(String, index=True)
    src_port = Column(Integer)
    dst_port = Column(Integer)
    protocol = Column(String)
    severity = Column(String, default="medium")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4
