# app/models.py


from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    severity = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, nullable=True)



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
