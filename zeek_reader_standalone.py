#!/usr/bin/env python3
"""
Standalone Zeek Log Reader Service

This script can be run independently on a Zeek sensor VM to read and process
Zeek logs without requiring the full backend setup.

Usage:
    python zeek_reader_standalone.py

Environment Variables:
    POSTGRES_URL: PostgreSQL connection string
    ZEEK_LOG_DIR: Directory containing Zeek logs
    ZEEK_PROCESSED_DIR: Directory for processed logs
    ZEEK_POLL_INTERVAL: Poll interval in seconds
"""

import os
import sys
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Try to import asyncpg
try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg not installed. Install with: pip install asyncpg")
    sys.exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("DEBUG: dotenv loaded")
except ImportError:
    print("DEBUG: dotenv not imported")
    pass  # dotenv not required, but recommended

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('zeek-log-reader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:pass@localhost:5432/cybercyte_db"
)
print(f"DEBUG: POSTGRES_URL from env: {os.getenv('POSTGRES_URL')}")
print(f"DEBUG: Using POSTGRES_URL: {POSTGRES_URL}")
ZEEK_LOG_DIR = os.getenv("ZEEK_LOG_DIR", "/opt/zeek/logs/current")
ZEEK_PROCESSED_DIR = os.getenv("ZEEK_PROCESSED_DIR", "/opt/zeek/logs/processed")
POLL_INTERVAL = int(os.getenv("ZEEK_POLL_INTERVAL", "10"))

db_pool: Optional[asyncpg.Pool] = None


async def init_db():
    """Initialize database connection and tables."""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)
        logger.info("Connected to PostgreSQL")
        
        # Create tables
        create_sql = """
        CREATE TABLE IF NOT EXISTS zeek_events (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            log_type VARCHAR(50) NOT NULL,
            source_ip INET,
            dest_ip INET,
            source_port INTEGER,
            dest_port INTEGER,
            protocol VARCHAR(20),
            event_text TEXT,
            severity VARCHAR(20) DEFAULT 'info',
            raw_data JSONB NOT NULL,
            host_id VARCHAR(255),
            processed BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_zeek_timestamp ON zeek_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_zeek_src_ip ON zeek_events(source_ip);
        CREATE INDEX IF NOT EXISTS idx_zeek_dst_ip ON zeek_events(dest_ip);
        CREATE INDEX IF NOT EXISTS idx_zeek_log_type ON zeek_events(log_type);
        
        CREATE TABLE IF NOT EXISTS zeek_connections (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid VARCHAR(50),
            source_ip INET NOT NULL,
            dest_ip INET NOT NULL,
            source_port INTEGER NOT NULL,
            dest_port INTEGER NOT NULL,
            protocol VARCHAR(10) NOT NULL,
            bytes_sent BIGINT DEFAULT 0,
            bytes_received BIGINT DEFAULT 0,
            connection_state VARCHAR(20),
            raw_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_conn_timestamp ON zeek_connections(timestamp);
        
        CREATE TABLE IF NOT EXISTS zeek_dns (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid VARCHAR(50),
            source_ip INET NOT NULL,
            dest_ip INET NOT NULL,
            source_port INTEGER NOT NULL,
            dest_port INTEGER NOT NULL,
            query VARCHAR(255),
            query_type VARCHAR(10),
            rcode VARCHAR(20),
            answers TEXT[],
            raw_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_dns_timestamp ON zeek_dns(timestamp);
        CREATE INDEX IF NOT EXISTS idx_dns_query ON zeek_dns(query);
        """
        
        async with db_pool.acquire() as conn:
            await conn.execute(create_sql)
        logger.info("Database tables verified")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def insert_event(log_type: str, data: Dict):
    """Insert a Zeek event."""
    if not db_pool:
        return
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO zeek_events 
                   (log_type, source_ip, dest_ip, source_port, dest_port, 
                    protocol, event_text, severity, raw_data)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                log_type,
                data.get("id.orig_h"),
                data.get("id.resp_h"),
                data.get("id.orig_p"),
                data.get("id.resp_p"),
                data.get("proto"),
                str(data),
                "info",
                json.dumps(data)
            )
    except Exception as e:
        logger.warning(f"Failed to insert event: {e}")


async def insert_connection(data: Dict):
    """Insert a connection event."""
    if not db_pool:
        return
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO zeek_connections
                   (uid, source_ip, dest_ip, source_port, dest_port, protocol,
                    bytes_sent, bytes_received, connection_state, raw_data)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                data.get("uid"),
                data.get("id.orig_h"),
                data.get("id.resp_h"),
                data.get("id.orig_p"),
                data.get("id.resp_p"),
                data.get("proto"),
                data.get("orig_bytes", 0),
                data.get("resp_bytes", 0),
                data.get("conn_state"),
                json.dumps(data)
            )
    except Exception as e:
        logger.warning(f"Failed to insert connection: {e}")


async def insert_dns(data: Dict):
    """Insert a DNS event."""
    if not db_pool:
        return
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO zeek_dns
                   (uid, source_ip, dest_ip, source_port, dest_port,
                    query, query_type, rcode, answers, raw_data)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                data.get("uid"),
                data.get("id.orig_h"),
                data.get("id.resp_h"),
                data.get("id.orig_p"),
                data.get("id.resp_p"),
                data.get("query"),
                data.get("qtype"),
                data.get("rcode"),
                data.get("answers", []),
                json.dumps(data)
            )
    except Exception as e:
        logger.warning(f"Failed to insert DNS: {e}")


async def process_file(file_path: Path):
    """Process a Zeek log file."""
    logger.info(f"Processing: {file_path.name}")
    
    try:
        log_type = file_path.stem  # Filename without extension
        count = 0
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Route to appropriate table
                if log_type == "conn":
                    await insert_connection(data)
                elif log_type == "dns":
                    await insert_dns(data)
                else:
                    await insert_event(log_type, data)
                
                count += 1
        
        logger.info(f"Processed {count} records from {file_path.name}")
        
        # Move to processed directory
        if ZEEK_PROCESSED_DIR:
            os.makedirs(ZEEK_PROCESSED_DIR, exist_ok=True)
            dest = Path(ZEEK_PROCESSED_DIR) / file_path.name
            file_path.rename(dest)
            logger.debug(f"Moved to: {dest}")
    
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")


async def monitor_logs():
    """Monitor Zeek log directory."""
    logger.info(f"Starting monitor on: {ZEEK_LOG_DIR}")
    os.makedirs(ZEEK_LOG_DIR, exist_ok=True)
    
    processed = set()
    
    while True:
        try:
            log_dir = Path(ZEEK_LOG_DIR)
            for log_file in log_dir.glob("*.log"):
                if log_file not in processed:
                    await process_file(log_file)
                    processed.add(log_file)
            
            await asyncio.sleep(POLL_INTERVAL)
        
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            await asyncio.sleep(POLL_INTERVAL)


async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Zeek Log Reader Service Started")
    logger.info(f"PostgreSQL: {POSTGRES_URL}")
    logger.info(f"Log Directory: {ZEEK_LOG_DIR}")
    logger.info(f"Poll Interval: {POLL_INTERVAL}s")
    logger.info("=" * 60)
    
    try:
        await init_db()
        await monitor_logs()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        global db_pool
        if db_pool:
            await db_pool.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
