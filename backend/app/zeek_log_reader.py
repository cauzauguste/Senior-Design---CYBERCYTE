"""
Zeek Log Reader Service

This service monitors a directory for Zeek log files, parses them, and sends
the parsed events to a PostgreSQL database. This can run on a separate VM
from the main application.

Zeek logs are typically JSON format or tab-separated format. This reader
handles both formats and extracts relevant security events.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import asyncpg
import ssl
import paramiko
from asyncio import to_thread
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
ZEEK_LOG_DIR = os.getenv("ZEEK_LOG_DIR", "/opt/zeek/logs/current")
ZEEK_PROCESSED_DIR = os.getenv("ZEEK_PROCESSED_DIR", "/opt/zeek/logs/processed")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:pass@localhost:5432/cybercyte_db")
POSTGRES_CA_FILE = os.getenv("POSTGRES_CA_FILE", None)
POLL_INTERVAL = int(os.getenv("ZEEK_POLL_INTERVAL", "10"))  # seconds
# Optional remote Zeek host configuration (SFTP)
ZEEK_REMOTE_HOST = os.getenv("ZEEK_REMOTE_HOST", None)
ZEEK_REMOTE_PORT = int(os.getenv("ZEEK_REMOTE_PORT", "22"))
ZEEK_REMOTE_USER = os.getenv("ZEEK_REMOTE_USER", None)
ZEEK_REMOTE_PATH = os.getenv("ZEEK_REMOTE_PATH", "/opt/zeek/logs/current")
ZEEK_REMOTE_PROCESSED = os.getenv("ZEEK_REMOTE_PROCESSED", None)
ZEEK_SSH_KEY = os.getenv("ZEEK_SSH_KEY", None)  # path to private key
ZEEK_SSH_PASSWORD = os.getenv("ZEEK_SSH_PASSWORD", None)
ZEEK_REMOVE_REMOTE = os.getenv("ZEEK_REMOVE_REMOTE", "false").lower() in ("1", "true", "yes")

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


async def init_db_pool():
    """Initialize the PostgreSQL connection pool."""
    global db_pool
    try:
        connect_args = {}
        if POSTGRES_CA_FILE and os.path.exists(POSTGRES_CA_FILE):
            connect_args['ssl'] = ssl.create_default_context(cafile=POSTGRES_CA_FILE)
        
        db_pool = await asyncpg.create_pool(
            POSTGRES_URL,
            min_size=1,
            max_size=10,
            **connect_args
        )
        logger.info("PostgreSQL connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise


async def close_db_pool():
    """Close the PostgreSQL connection pool."""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("PostgreSQL connection pool closed")


async def ensure_zeek_tables_exist():
    """Create necessary tables if they don't exist."""
    if not db_pool:
        raise RuntimeError("Database pool not initialized")
    
    create_tables_sql = """
    -- Main Zeek events table
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
    
    CREATE INDEX IF NOT EXISTS idx_zeek_events_timestamp ON zeek_events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_zeek_events_source_ip ON zeek_events(source_ip);
    CREATE INDEX IF NOT EXISTS idx_zeek_events_dest_ip ON zeek_events(dest_ip);
    CREATE INDEX IF NOT EXISTS idx_zeek_events_log_type ON zeek_events(log_type);
    CREATE INDEX IF NOT EXISTS idx_zeek_events_host_id ON zeek_events(host_id);
    
    -- Connection tracking table
    CREATE TABLE IF NOT EXISTS zeek_connections (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        uid VARCHAR(50),
        source_ip INET NOT NULL,
        dest_ip INET NOT NULL,
        source_port INTEGER NOT NULL,
        dest_port INTEGER NOT NULL,
        protocol VARCHAR(10) NOT NULL,
        duration INTERVAL,
        bytes_sent BIGINT DEFAULT 0,
        bytes_received BIGINT DEFAULT 0,
        connection_state VARCHAR(20),
        raw_data JSONB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_zeek_conn_timestamp ON zeek_connections(timestamp);
    CREATE INDEX IF NOT EXISTS idx_zeek_conn_source_ip ON zeek_connections(source_ip);
    CREATE INDEX IF NOT EXISTS idx_zeek_conn_dest_ip ON zeek_connections(dest_ip);
    
    -- DNS events
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
    
    CREATE INDEX IF NOT EXISTS idx_zeek_dns_timestamp ON zeek_dns(timestamp);
    CREATE INDEX IF NOT EXISTS idx_zeek_dns_query ON zeek_dns(query);
    
    -- File integrity table
    CREATE TABLE IF NOT EXISTS zeek_files (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        uid VARCHAR(50),
        file_id VARCHAR(255),
        file_name VARCHAR(255),
        file_size BIGINT,
        file_mime_type VARCHAR(100),
        md5_hash VARCHAR(32),
        sha1_hash VARCHAR(40),
        sha256_hash VARCHAR(64),
        raw_data JSONB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_zeek_files_timestamp ON zeek_files(timestamp);
    CREATE INDEX IF NOT EXISTS idx_zeek_files_md5 ON zeek_files(md5_hash);
    CREATE INDEX IF NOT EXISTS idx_zeek_files_sha256 ON zeek_files(sha256_hash);
    """
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(create_tables_sql)
        logger.info("Zeek tables created/verified")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


def parse_zeek_json_line(line: str) -> Optional[Dict]:
    """Parse a single line of Zeek JSON log format."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def parse_zeek_log_line(line: str, separator: str = "\t") -> Optional[Dict]:
    """Parse a single line of Zeek tab-separated log format."""
    # Zeek logs often have headers with metadata
    if line.startswith("#"):
        return None
    
    try:
        # This is a simplified parser - adjust based on your Zeek configuration
        parts = line.split(separator)
        if len(parts) < 3:
            return None
        return {"raw": line, "parts": parts}
    except Exception as e:
        logger.debug(f"Failed to parse log line: {e}")
        return None


async def insert_zeek_event(
    log_type: str,
    source_ip: Optional[str],
    dest_ip: Optional[str],
    source_port: Optional[int],
    dest_port: Optional[int],
    protocol: Optional[str],
    event_text: Optional[str],
    severity: str,
    raw_data: Dict,
    host_id: Optional[str] = None
):
    """Insert a parsed Zeek event into the database."""
    if not db_pool:
        raise RuntimeError("Database pool not initialized")
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO zeek_events 
                (log_type, source_ip, dest_ip, source_port, dest_port, protocol, 
                 event_text, severity, raw_data, host_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                log_type, source_ip, dest_ip, source_port, dest_port, protocol,
                event_text, severity, json.dumps(raw_data), host_id
            )
        logger.debug(f"Inserted Zeek event: {log_type} from {source_ip}")
    except Exception as e:
        logger.error(f"Failed to insert Zeek event: {e}")


async def insert_connection(conn_data: Dict):
    """Insert a connection event from Zeek conn.log."""
    if not db_pool:
        raise RuntimeError("Database pool not initialized")
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO zeek_connections
                (uid, source_ip, dest_ip, source_port, dest_port, protocol,
                 duration, bytes_sent, bytes_received, connection_state, raw_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                conn_data.get("uid"),
                conn_data.get("id.orig_h"),
                conn_data.get("id.resp_h"),
                conn_data.get("id.orig_p"),
                conn_data.get("id.resp_p"),
                conn_data.get("proto"),
                conn_data.get("duration"),
                conn_data.get("orig_bytes", 0),
                conn_data.get("resp_bytes", 0),
                conn_data.get("conn_state"),
                json.dumps(conn_data)
            )
        logger.debug(f"Inserted connection: {conn_data.get('uid')}")
    except Exception as e:
        logger.error(f"Failed to insert connection: {e}")


async def insert_dns_event(dns_data: Dict):
    """Insert a DNS event from Zeek dns.log."""
    if not db_pool:
        raise RuntimeError("Database pool not initialized")
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO zeek_dns
                (uid, source_ip, dest_ip, source_port, dest_port,
                 query, query_type, rcode, answers, raw_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                dns_data.get("uid"),
                dns_data.get("id.orig_h"),
                dns_data.get("id.resp_h"),
                dns_data.get("id.orig_p"),
                dns_data.get("id.resp_p"),
                dns_data.get("query"),
                dns_data.get("qtype"),
                dns_data.get("rcode"),
                dns_data.get("answers", []),
                json.dumps(dns_data)
            )
        logger.debug(f"Inserted DNS event: {dns_data.get('query')}")
    except Exception as e:
        logger.error(f"Failed to insert DNS event: {e}")


async def process_zeek_log_file(file_path: Path):
    """Process a single Zeek log file."""
    logger.info(f"Processing Zeek log file: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                
                # Try to parse as JSON first
                parsed = parse_zeek_json_line(line)
                if parsed:
                    # Determine log type and process accordingly
                    log_type = file_path.stem  # filename without extension
                    
                    if log_type == "conn":
                        await insert_connection(parsed)
                    elif log_type == "dns":
                        await insert_dns_event(parsed)
                    else:
                        # Generic event
                        await insert_zeek_event(
                            log_type=log_type,
                            source_ip=parsed.get("id.orig_h"),
                            dest_ip=parsed.get("id.resp_h"),
                            source_port=parsed.get("id.orig_p"),
                            dest_port=parsed.get("id.resp_p"),
                            protocol=parsed.get("proto"),
                            event_text=str(parsed),
                            severity="info",
                            raw_data=parsed
                        )
        
        logger.info(f"Successfully processed: {file_path}")
        
        # Move to processed directory if configured
        if ZEEK_PROCESSED_DIR:
            os.makedirs(ZEEK_PROCESSED_DIR, exist_ok=True)
            dest_path = Path(ZEEK_PROCESSED_DIR) / file_path.name
            file_path.rename(dest_path)
            logger.debug(f"Moved file to: {dest_path}")
    
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")


async def monitor_zeek_logs():
    """Monitor the Zeek log directory and process new log files."""
    logger.info(f"Starting Zeek log monitor on directory: {ZEEK_LOG_DIR}")
    
    # Ensure directories exist
    os.makedirs(ZEEK_LOG_DIR, exist_ok=True)
    if ZEEK_PROCESSED_DIR:
        os.makedirs(ZEEK_PROCESSED_DIR, exist_ok=True)
    
    # Track processed files to avoid reprocessing
    processed_files = set()
    
    while True:
        try:
            # If configured, fetch remote Zeek logs via SFTP into local ZEEK_LOG_DIR
            if ZEEK_REMOTE_HOST and ZEEK_REMOTE_USER:
                try:
                    await fetch_remote_logs_via_sftp()
                except Exception as e:
                    logger.error(f"Failed to fetch remote logs: {e}")

            # Look for new Zeek log files
            log_dir = Path(ZEEK_LOG_DIR)
            
            # Zeek log files typically have .log extension
            for log_file in log_dir.glob("*.log"):
                if log_file not in processed_files:
                    await process_zeek_log_file(log_file)
                    processed_files.add(log_file)
            
            # Wait before next poll
            await asyncio.sleep(POLL_INTERVAL)
        
        except Exception as e:
            logger.error(f"Error in log monitor loop: {e}")
            await asyncio.sleep(POLL_INTERVAL)


async def fetch_remote_logs_via_sftp():
    """Fetch Zeek log files from a remote host via SFTP into the local ZEEK_LOG_DIR.

    This runs blocking SFTP operations in a thread to avoid blocking the event loop.
    """
    logger.info(f"Attempting SFTP fetch from {ZEEK_REMOTE_USER}@{ZEEK_REMOTE_HOST}:{ZEEK_REMOTE_PATH}")

    def _sftp_fetch():
        transport = None
        sftp = None
        try:
            if ZEEK_SSH_KEY:
                key = paramiko.RSAKey.from_private_key_file(ZEEK_SSH_KEY)
                transport = paramiko.Transport((ZEEK_REMOTE_HOST, ZEEK_REMOTE_PORT))
                transport.connect(username=ZEEK_REMOTE_USER, pkey=key)
            else:
                transport = paramiko.Transport((ZEEK_REMOTE_HOST, ZEEK_REMOTE_PORT))
                transport.connect(username=ZEEK_REMOTE_USER, password=ZEEK_SSH_PASSWORD)

            sftp = paramiko.SFTPClient.from_transport(transport)

            # Ensure local dir exists
            os.makedirs(ZEEK_LOG_DIR, exist_ok=True)

            # List remote files
            for entry in sftp.listdir_attr(ZEEK_REMOTE_PATH):
                filename = entry.filename
                if not filename.endswith('.log'):
                    continue

                remote_file = f"{ZEEK_REMOTE_PATH.rstrip('/')}/{filename}"
                local_file = os.path.join(ZEEK_LOG_DIR, filename)

                # Skip if already present locally
                if os.path.exists(local_file):
                    continue

                logger.info(f"Downloading remote Zeek log: {remote_file} -> {local_file}")
                try:
                    sftp.get(remote_file, local_file)
                    # Optionally move or remove remote file
                    if ZEEK_REMOTE_PROCESSED:
                        remote_processed_path = f"{ZEEK_REMOTE_PROCESSED.rstrip('/')}/{filename}"
                        try:
                            # Try to move remote file
                            sftp.rename(remote_file, remote_processed_path)
                        except IOError:
                            # Fall back to removing if rename not possible
                            if ZEEK_REMOVE_REMOTE:
                                sftp.remove(remote_file)
                    else:
                        if ZEEK_REMOVE_REMOTE:
                            sftp.remove(remote_file)
                except Exception as ex:
                    logger.error(f"Failed to download remote file {remote_file}: {ex}")

        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if transport:
                    transport.close()
            except Exception:
                pass

    # Run blocking SFTP operations in a thread
    await to_thread(_sftp_fetch)


async def main():
    """Main entry point."""
    try:
        # Initialize database
        await init_db_pool()
        await ensure_zeek_tables_exist()
        
        # Start monitoring Zeek logs
        await monitor_zeek_logs()
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
