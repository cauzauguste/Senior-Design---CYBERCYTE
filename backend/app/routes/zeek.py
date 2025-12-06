"""
Zeek events API routes

Provides endpoints for querying parsed Zeek security events from the database.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import List, Optional
from backend.app.database import get_db
from backend.app import models
from backend.app.schemas import ZeekEventSchema

router = APIRouter()


@router.get("/events/zeek/all", tags=["Zeek Events"])
async def get_all_zeek_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get all Zeek events with pagination."""
    try:
        events = db.query(models.ZeekEvent)\
            .order_by(desc(models.ZeekEvent.timestamp))\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        total = db.query(models.ZeekEvent).count()
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/connections", tags=["Zeek Events"])
async def get_zeek_connections(
    limit: int = Query(100, ge=1, le=1000),
    source_ip: Optional[str] = Query(None),
    dest_ip: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get Zeek connection events with optional filtering."""
    try:
        query = db.query(models.ZeekConnection).order_by(desc(models.ZeekConnection.timestamp))
        
        if source_ip:
            query = query.filter(models.ZeekConnection.source_ip == source_ip)
        if dest_ip:
            query = query.filter(models.ZeekConnection.dest_ip == dest_ip)
        
        events = query.limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/dns", tags=["Zeek Events"])
async def get_zeek_dns_events(
    limit: int = Query(100, ge=1, le=1000),
    query_string: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get Zeek DNS events with optional query filtering."""
    try:
        query = db.query(models.ZeekDNS).order_by(desc(models.ZeekDNS.timestamp))
        
        if query_string:
            query = query.filter(models.ZeekDNS.query.ilike(f"%{query_string}%"))
        
        events = query.limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/files", tags=["Zeek Events"])
async def get_zeek_files(
    limit: int = Query(100, ge=1, le=1000),
    hash_type: str = Query("sha256"),
    hash_value: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get Zeek file events with hash filtering."""
    try:
        query = db.query(models.ZeekFile).order_by(desc(models.ZeekFile.timestamp))
        
        if hash_value:
            if hash_type == "md5":
                query = query.filter(models.ZeekFile.md5_hash == hash_value)
            elif hash_type == "sha1":
                query = query.filter(models.ZeekFile.sha1_hash == hash_value)
            elif hash_type == "sha256":
                query = query.filter(models.ZeekFile.sha256_hash == hash_value)
        
        events = query.limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "hash_type": hash_type,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/http", tags=["Zeek Events"])
async def get_zeek_http_events(
    limit: int = Query(100, ge=1, le=1000),
    uri: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get Zeek HTTP events with optional URI filtering."""
    try:
        query = db.query(models.ZeekHTTP).order_by(desc(models.ZeekHTTP.timestamp))
        
        if uri:
            query = query.filter(models.ZeekHTTP.uri.ilike(f"%{uri}%"))
        
        events = query.limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/ssl", tags=["Zeek Events"])
async def get_zeek_ssl_events(
    limit: int = Query(100, ge=1, le=1000),
    server_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get Zeek SSL/TLS events with optional filtering."""
    try:
        query = db.query(models.ZeekSSL).order_by(desc(models.ZeekSSL.timestamp))
        
        if server_name:
            query = query.filter(models.ZeekSSL.server_name.ilike(f"%{server_name}%"))
        
        events = query.limit(limit).all()
        total = query.count()
        
        return {
            "total": total,
            "limit": limit,
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/stats", tags=["Zeek Events"])
async def get_zeek_stats(
    hours: int = Query(24, ge=1),
    db: Session = Depends(get_db)
):
    """Get Zeek event statistics for the past N hours."""
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        total_events = db.query(models.ZeekEvent)\
            .filter(models.ZeekEvent.timestamp >= time_threshold).count()
        
        total_connections = db.query(models.ZeekConnection)\
            .filter(models.ZeekConnection.timestamp >= time_threshold).count()
        
        total_dns = db.query(models.ZeekDNS)\
            .filter(models.ZeekDNS.timestamp >= time_threshold).count()
        
        total_files = db.query(models.ZeekFile)\
            .filter(models.ZeekFile.timestamp >= time_threshold).count()
        
        total_http = db.query(models.ZeekHTTP)\
            .filter(models.ZeekHTTP.timestamp >= time_threshold).count()
        
        total_ssl = db.query(models.ZeekSSL)\
            .filter(models.ZeekSSL.timestamp >= time_threshold).count()
        
        return {
            "time_range_hours": hours,
            "timestamp": datetime.utcnow(),
            "stats": {
                "total_events": total_events,
                "total_connections": total_connections,
                "total_dns_queries": total_dns,
                "total_files": total_files,
                "total_http_requests": total_http,
                "total_ssl_connections": total_ssl
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/by-type", tags=["Zeek Events"])
async def get_zeek_events_by_type(
    log_type: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get Zeek events filtered by log type."""
    try:
        events = db.query(models.ZeekEvent)\
            .filter(models.ZeekEvent.log_type == log_type)\
            .order_by(desc(models.ZeekEvent.timestamp))\
            .limit(limit)\
            .all()
        
        return {
            "log_type": log_type,
            "count": len(events),
            "events": events
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/zeek/suspicious-ips", tags=["Zeek Events"])
async def get_suspicious_ips(
    hours: int = Query(24, ge=1),
    min_events: int = Query(10, ge=1),
    db: Session = Depends(get_db)
):
    """Get IPs that have triggered multiple security events."""
    try:
        from sqlalchemy import func
        
        time_threshold = datetime.utcnow() - timedelta(hours=hours)
        
        # Get source IPs with multiple events
        suspicious_sources = db.query(
            models.ZeekEvent.source_ip,
            func.count(models.ZeekEvent.id).label("event_count")
        ).filter(
            models.ZeekEvent.timestamp >= time_threshold,
            models.ZeekEvent.source_ip.isnot(None)
        ).group_by(
            models.ZeekEvent.source_ip
        ).having(
            func.count(models.ZeekEvent.id) >= min_events
        ).order_by(
            desc(func.count(models.ZeekEvent.id))
        ).limit(50).all()
        
        return {
            "time_range_hours": hours,
            "min_events_threshold": min_events,
            "suspicious_sources": [
                {"ip": ip, "event_count": count} for ip, count in suspicious_sources
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
