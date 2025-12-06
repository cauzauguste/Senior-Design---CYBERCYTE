"""
Remote Zeek Integration Routes

Provides FastAPI endpoints for:
1. Retrieving logs from remote Zeek VM (35.222.249.202)
2. Parsing and ingesting into PostgreSQL (34.132.194.35)
3. Health checks for connectivity
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import Optional
import logging

from backend.app.zeek_remote_client import ZeekRemoteClient, PostgresIngester

router = APIRouter()
logger = logging.getLogger(__name__)

# Global clients (lazy initialized)
zeek_client: Optional[ZeekRemoteClient] = None
postgres_ingester: Optional[PostgresIngester] = None


async def ensure_clients():
    """Ensure clients are initialized."""
    global zeek_client, postgres_ingester
    
    if zeek_client is None:
        zeek_client = ZeekRemoteClient()
    
    if postgres_ingester is None:
        postgres_ingester = PostgresIngester()
        if not await postgres_ingester.init_pool():
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize PostgreSQL connection"
            )
        try:
            await postgres_ingester.ensure_tables()
        except Exception as e:
            logger.error(f"Failed to ensure tables: {e}")
            raise HTTPException(status_code=500, detail="Database setup failed")


@router.get("/zeek/remote/health", tags=["Zeek Remote Integration"])
async def zeek_remote_health():
    """
    Health check for remote Zeek VM connectivity.
    Tests connection to 35.222.249.202 and 34.132.194.35 (PostgreSQL).
    """
    try:
        await ensure_clients()
        
        # Test Zeek VM connection
        zeek_connected = await zeek_client.connect()
        zeek_status = "connected" if zeek_connected else "disconnected"
        
        # Test PostgreSQL connection
        postgres_pool_status = postgres_ingester.pool is not None
        
        health = {
            "zeek_vm": {
                "host": zeek_client.host,
                "port": zeek_client.port,
                "status": zeek_status
            },
            "postgres_vm": {
                "host": postgres_ingester.db_url.split('@')[1].split(':')[0] if '@' in postgres_ingester.db_url else 'unknown',
                "status": "available" if postgres_pool_status else "unavailable"
            },
            "overall": "healthy" if zeek_connected and postgres_pool_status else "unhealthy"
        }
        
        if zeek_connected:
            await zeek_client.disconnect()
        
        return health
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zeek/remote/list-logs", tags=["Zeek Remote Integration"])
async def list_remote_logs():
    """
    List all Zeek log files available on remote Zeek VM (35.222.249.202).
    """
    try:
        await ensure_clients()
        
        # Connect to Zeek VM
        connected = await zeek_client.connect()
        if not connected:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot connect to Zeek VM at {zeek_client.host}:{zeek_client.port}"
            )
        
        # List files
        files = await zeek_client.list_log_files()
        await zeek_client.disconnect()
        
        return {
            "zeek_vm": zeek_client.host,
            "remote_path": zeek_client.remote_path,
            "log_files": files,
            "count": len(files)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list remote logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zeek/remote/ingest-log", tags=["Zeek Remote Integration"])
async def ingest_single_log(
    filename: str = Query(..., description="Log filename to ingest (e.g., 'conn.log')"),
    background_tasks: BackgroundTasks = None
):
    """
    Retrieve a single Zeek log file from remote VM and ingest into PostgreSQL.
    
    Steps:
    1. Connect to Zeek VM (35.222.249.202) via SFTP
    2. Download the specified log file
    3. Parse Zeek JSON events
    4. Insert into PostgreSQL (34.132.194.35)
    
    Example: /zeek/remote/ingest-log?filename=conn.log
    """
    try:
        await ensure_clients()
        
        logger.info(f"Starting ingestion of {filename} from Zeek VM")
        
        # Connect to Zeek VM
        connected = await zeek_client.connect()
        if not connected:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot connect to Zeek VM at {zeek_client.host}:{zeek_client.port}"
            )
        
        # Retrieve log content
        log_content = await zeek_client.get_log_content(filename)
        if log_content is None:
            await zeek_client.disconnect()
            raise HTTPException(
                status_code=404,
                detail=f"Log file {filename} not found on Zeek VM"
            )
        
        # Parse and ingest
        lines_processed, lines_inserted = await postgres_ingester.parse_and_ingest_log_content(
            log_content,
            filename
        )
        
        await zeek_client.disconnect()
        
        return {
            "status": "success",
            "zeek_vm": zeek_client.host,
            "postgres_vm": postgres_ingester.db_url.split('@')[1].split(':')[0] if '@' in postgres_ingester.db_url else 'unknown',
            "filename": filename,
            "lines_processed": lines_processed,
            "lines_inserted": lines_inserted,
            "message": f"Ingested {lines_inserted} events from {filename}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to ingest log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zeek/remote/ingest-all", tags=["Zeek Remote Integration"])
async def ingest_all_logs(background_tasks: BackgroundTasks):
    """
    Retrieve ALL Zeek log files from remote VM and ingest into PostgreSQL.
    
    This runs in background. Check status with /zeek/remote/ingest-status
    """
    try:
        await ensure_clients()
        
        logger.info("Starting bulk ingestion of all Zeek logs from remote VM")
        
        # Run ingestion in background
        background_tasks.add_task(_bulk_ingest)
        
        return {
            "status": "ingestion_started",
            "message": "Bulk log ingestion started in background",
            "check_endpoint": "/zeek/remote/ingest-status"
        }
    
    except Exception as e:
        logger.error(f"Failed to start bulk ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _bulk_ingest():
    """Background task for bulk ingestion."""
    try:
        await ensure_clients()
        
        # Connect to Zeek VM
        connected = await zeek_client.connect()
        if not connected:
            logger.error(f"Cannot connect to Zeek VM at {zeek_client.host}:{zeek_client.port}")
            return
        
        # List all files
        files = await zeek_client.list_log_files()
        
        total_processed = 0
        total_inserted = 0
        
        # Ingest each file
        for filename in files:
            try:
                log_content = await zeek_client.get_log_content(filename)
                if log_content:
                    processed, inserted = await postgres_ingester.parse_and_ingest_log_content(
                        log_content,
                        filename
                    )
                    total_processed += processed
                    total_inserted += inserted
            except Exception as e:
                logger.error(f"Failed to ingest {filename}: {e}")
                continue
        
        await zeek_client.disconnect()
        logger.info(f"Bulk ingestion complete: {total_processed} lines processed, {total_inserted} inserted")
    
    except Exception as e:
        logger.error(f"Bulk ingestion failed: {e}")


@router.get("/zeek/remote/test-connection", tags=["Zeek Remote Integration"])
async def test_connections():
    """
    Test and diagnose connectivity to both Zeek VM and PostgreSQL VM.
    Provides detailed connection information for troubleshooting.
    """
    try:
        await ensure_clients()
        
        diagnostics = {
            "zeek_vm": {
                "host": zeek_client.host,
                "port": zeek_client.port,
                "username": zeek_client.username,
                "remote_path": zeek_client.remote_path
            },
            "postgres_vm": {
                "url": postgres_ingester.db_url
            },
            "connectivity": {}
        }
        
        # Test Zeek connection
        try:
            zeek_ok = await zeek_client.connect()
            if zeek_ok:
                files = await zeek_client.list_log_files()
                diagnostics["connectivity"]["zeek_vm"] = {
                    "status": "connected",
                    "log_files_found": len(files),
                    "sample_files": files[:5] if files else []
                }
                await zeek_client.disconnect()
            else:
                diagnostics["connectivity"]["zeek_vm"] = {
                    "status": "failed",
                    "error": "SFTP authentication failed"
                }
        except Exception as e:
            diagnostics["connectivity"]["zeek_vm"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Test PostgreSQL connection
        try:
            if postgres_ingester.pool:
                async with postgres_ingester.pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    diagnostics["connectivity"]["postgres_vm"] = {
                        "status": "connected",
                        "version": version[:50] + "..." if len(version) > 50 else version
                    }
            else:
                diagnostics["connectivity"]["postgres_vm"] = {
                    "status": "pool_not_initialized"
                }
        except Exception as e:
            diagnostics["connectivity"]["postgres_vm"] = {
                "status": "error",
                "error": str(e)
            }
        
        return diagnostics
    
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zeek/remote/query-tables", tags=["Zeek Remote Integration"])
async def query_tables():
    """
    Query and provide information about Zeek-related tables in PostgreSQL.
    
    This includes:
    - List of tables
    - Sample records from zeek_connections
    - Count of records in zeek_connections
    - Top 10 connections by bytes transferred
    - Connection count grouped by protocol
    - Connections to/from a specific IP (10.128.0.6)
    """
    try:
        await ensure_clients()
        
        # Connect to PostgreSQL
        async with postgres_ingester.pool.acquire() as conn:
            # List all tables
            tables = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            
            # Describe zeek_conn table
            zeek_connections_description = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'zeek_conn'
            """)
            
            # Count records
            zeek_connections_count = await conn.fetchval("SELECT COUNT(*) FROM zeek_conn")
            
            # Show all connections
            all_connections = await conn.fetch("""
                SELECT 
                    log->>'uid' as uid,
                    log->>'id.orig_h' as source_ip,
                    log->>'id.resp_h' as dest_ip,
                    (log->>'id.orig_p')::int as source_port,
                    (log->>'id.resp_p')::int as dest_port,
                    log->>'proto' as protocol
                FROM zeek_conn
            """)
            
            # Show top 10 by bytes transferred
            top_connections = await conn.fetch("""
                SELECT 
                    log->>'uid' as uid,
                    log->>'id.orig_h' as source_ip,
                    log->>'id.resp_h' as dest_ip,
                    ((log->>'orig_bytes')::bigint + (log->>'resp_bytes')::bigint) as total_bytes
                FROM zeek_conn
                ORDER BY total_bytes DESC
                LIMIT 10
            """)
            
            # Group by protocol
            connections_by_protocol = await conn.fetch("""
                SELECT log->>'proto' as protocol, COUNT(*) as count
                FROM zeek_conn
                GROUP BY protocol
            """)
            
            # Show connections to/from specific IP
            specific_ip_connections = await conn.fetch("""
                SELECT * FROM zeek_conn 
                WHERE log->>'id.orig_h' = '10.128.0.6' OR log->>'id.resp_h' = '10.128.0.6'
            """)
        
        return {
            "status": "success",
            "tables": [table["table_name"] for table in tables],
            "zeek_connections": {
                "description": zeek_connections_description,
                "count": zeek_connections_count,
                "all_records": all_connections,
                "top_records": top_connections,
                "connections_by_protocol": connections_by_protocol,
                "specific_ip_connections": specific_ip_connections
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to query tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))
