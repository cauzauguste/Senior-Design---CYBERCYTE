# models.py
from app.database import Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    src_ip = Column(String, index=True)
    dst_ip = Column(String, index=True)
    src_port = Column(Integer)
    dst_port = Column(Integer)
    protocol = Column(String)
    severity = Column(String, default="medium")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
