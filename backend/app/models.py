# app/models.py


from sqlalchemy import Column, Integer, String, DateTime, JSON, BigInteger, Interval, Boolean
from sqlalchemy.dialects.postgresql import INET, ARRAY
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


# ============================================================================
# Zeek Log Models - for storing parsed Zeek security events
# ============================================================================

class ZeekEvent(Base):
    """Generic Zeek security events."""
    __tablename__ = "zeek_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    log_type = Column(String(50), nullable=False, index=True)
    source_ip = Column(String(45), index=True)  # IPv4 or IPv6
    dest_ip = Column(String(45), index=True)
    source_port = Column(Integer)
    dest_port = Column(Integer)
    protocol = Column(String(20))
    event_text = Column(String, nullable=True)
    severity = Column(String(20), default="info")
    raw_data = Column(JSON, nullable=False)
    host_id = Column(String(255), index=True, nullable=True)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeekConnection(Base):
    """Zeek connection tracking (from conn.log)."""
    __tablename__ = "zeek_connections"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uid = Column(String(50), index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    dest_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=False)
    dest_port = Column(Integer, nullable=False)
    protocol = Column(String(10), nullable=False)
    duration = Column(Interval)
    bytes_sent = Column(BigInteger, default=0)
    bytes_received = Column(BigInteger, default=0)
    connection_state = Column(String(20))
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeekDNS(Base):
    """Zeek DNS events (from dns.log)."""
    __tablename__ = "zeek_dns"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uid = Column(String(50), index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    dest_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer, nullable=False)
    dest_port = Column(Integer, nullable=False)
    query = Column(String(255), index=True)
    query_type = Column(String(10))
    rcode = Column(String(20))
    answers = Column(ARRAY(String), nullable=True)
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeekFile(Base):
    """Zeek file integrity and hashing (from files.log)."""
    __tablename__ = "zeek_files"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uid = Column(String(50), index=True)
    file_id = Column(String(255))
    file_name = Column(String(255), index=True)
    file_size = Column(BigInteger)
    file_mime_type = Column(String(100))
    md5_hash = Column(String(32), index=True)
    sha1_hash = Column(String(40), index=True)
    sha256_hash = Column(String(64), index=True)
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeekHTTP(Base):
    """Zeek HTTP events (from http.log)."""
    __tablename__ = "zeek_http"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uid = Column(String(50), index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    dest_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer)
    dest_port = Column(Integer)
    method = Column(String(20))
    uri = Column(String, index=True)
    referrer = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    status_code = Column(Integer)
    response_body_size = Column(BigInteger)
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ZeekSSL(Base):
    """Zeek SSL/TLS events (from ssl.log)."""
    __tablename__ = "zeek_ssl"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    uid = Column(String(50), index=True)
    source_ip = Column(String(45), nullable=False, index=True)
    dest_ip = Column(String(45), nullable=False, index=True)
    source_port = Column(Integer)
    dest_port = Column(Integer)
    version = Column(String(20))
    cipher = Column(String(100))
    server_name = Column(String(255), index=True)
    subject = Column(String)
    issuer = Column(String)
    established = Column(Boolean)
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

