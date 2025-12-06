"""
Zeek Remote Client Module

Allows FastAPI to connect to and retrieve Zeek logs from a remote Zeek VM via SFTP,
then parse and ingest them into PostgreSQL.

Configuration via environment variables:
- ZEEK_REMOTE_HOST: IP/hostname of Zeek VM (e.g., 35.222.249.202)
- ZEEK_REMOTE_PORT: SSH port (default: 22)
- ZEEK_REMOTE_USER: SSH username
- ZEEK_REMOTE_PATH: Path to Zeek logs on remote VM (e.g., /opt/zeek/logs/current)
- ZEEK_SSH_KEY: Path to private SSH key (or use ZEEK_SSH_PASSWORD)
- ZEEK_SSH_PASSWORD: SSH password (alternative to key)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from asyncio import to_thread
import paramiko
import asyncpg
import ssl
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
ZEEK_REMOTE_HOST = os.getenv("ZEEK_REMOTE_HOST", "34.59.146.67")
ZEEK_REMOTE_PORT = int(os.getenv("ZEEK_REMOTE_PORT", "22"))
ZEEK_REMOTE_USER = os.getenv("ZEEK_REMOTE_USER", "zauguste52")
ZEEK_REMOTE_PATH = os.getenv("ZEEK_REMOTE_PATH", "/opt/zeek/logs/current")
ZEEK_SSH_KEY = os.getenv("ZEEK_SSH_KEY", None)
ZEEK_SSH_PASSWORD = os.getenv("ZEEK_SSH_PASSWORD", None)

# PostgreSQL configuration (pointing to 34.132.194.35)
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:pass@34.132.194.35:5432/postgres")
POSTGRES_CA_FILE = os.getenv("POSTGRES_CA_FILE", None)


class ZeekRemoteClient:
    """Client for connecting to remote Zeek sensor VM and retrieving logs."""
    
    def __init__(self, 
                 host: str = ZEEK_REMOTE_HOST,
                 port: int = ZEEK_REMOTE_PORT,
                 username: str = ZEEK_REMOTE_USER,
                 remote_path: str = ZEEK_REMOTE_PATH,
                 ssh_key: Optional[str] = ZEEK_SSH_KEY,
                 ssh_password: Optional[str] = ZEEK_SSH_PASSWORD):
        """Initialize remote Zeek client."""
        self.host = host
        self.port = port
        self.username = username
        self.remote_path = remote_path
        self.ssh_key = ssh_key
        self.ssh_password = ssh_password
        self.sftp = None
        self.transport = None
        self.client = None
    
    async def connect(self) -> bool:
        """Establish SFTP connection to remote Zeek VM."""
        def _connect():
            try:
                # Use SSHClient which supports key_filename (ed25519, rsa, ecdsa)
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                connect_kwargs = dict(hostname=self.host, port=self.port, username=self.username, timeout=10)

                if self.ssh_key and os.path.exists(self.ssh_key):
                    # Use key file directly; paramiko will detect key type
                    connect_kwargs['key_filename'] = self.ssh_key
                    # Do not attempt agent/key discovery unless explicitly desired
                    connect_kwargs['look_for_keys'] = False
                    connect_kwargs['allow_agent'] = False
                else:
                    connect_kwargs['password'] = self.ssh_password or ""

                client.connect(**connect_kwargs)

                self.client = client
                self.transport = client.get_transport()
                self.sftp = client.open_sftp()

                logger.info(f"Connected to Zeek VM: {self.username}@{self.host}:{self.port}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to Zeek VM: {e}")
                return False
        
        return await to_thread(_connect)
    
    async def list_log_files(self) -> List[str]:
        """List available Zeek log files on remote VM."""
        def _list_files():
            try:
                if not self.sftp:
                    return []
                
                files = []
                for entry in self.sftp.listdir_attr(self.remote_path):
                    if entry.filename.endswith('.log'):
                        files.append(entry.filename)
                
                logger.info(f"Found {len(files)} Zeek log files on remote VM")
                return files
            except Exception as e:
                logger.error(f"Failed to list remote files: {e}")
                return []
        
        return await to_thread(_list_files)
    
    async def get_log_content(self, filename: str) -> Optional[str]:
        """Retrieve content of a specific Zeek log file from remote VM."""
        def _get_content():
            try:
                if not self.sftp:
                    logger.error("SFTP not connected")
                    return None
                
                remote_file = f"{self.remote_path.rstrip('/')}/{filename}"
                
                # Read file content into memory
                with self.sftp.file(remote_file, 'r') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                
                logger.info(f"Retrieved {len(content)} bytes from {remote_file}")
                return content
            except Exception as e:
                logger.error(f"Failed to get remote file content: {e}")
                return None
        
        return await to_thread(_get_content)
    
    async def disconnect(self):
        """Close SFTP and SSH connections."""
        def _disconnect():
            try:
                if self.sftp:
                    try:
                        self.sftp.close()
                    except Exception:
                        pass
                if self.transport:
                    try:
                        self.transport.close()
                    except Exception:
                        pass
                if self.client:
                    try:
                        self.client.close()
                    except Exception:
                        pass
                logger.info("Disconnected from Zeek VM")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
        
        await to_thread(_disconnect)


class PostgresIngester:
    """Handles parsing Zeek logs and inserting into PostgreSQL."""
    
    def __init__(self, db_url: str = POSTGRES_URL, ca_file: Optional[str] = POSTGRES_CA_FILE):
        """Initialize PostgreSQL ingester."""
        self.db_url = db_url
        self.ca_file = ca_file
        self.pool: Optional[asyncpg.Pool] = None
    
    async def init_pool(self) -> bool:
        """Initialize database connection pool."""
        try:
            connect_args = {}
            if self.ca_file and os.path.exists(self.ca_file):
                connect_args['ssl'] = ssl.create_default_context(cafile=self.ca_file)
            
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=5,
                **connect_args
            )
            logger.info("PostgreSQL connection pool initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            return False
    
    async def close_pool(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")
    
    async def ensure_tables(self):
        """Create necessary Zeek event tables if they don't exist."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        create_tables_sql = """
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
        
        CREATE TABLE IF NOT EXISTS zeek_conn (
            id SERIAL PRIMARY KEY,
            log JSONB NOT NULL,
            inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_zeek_conn_inserted_at ON zeek_conn(inserted_at);
        
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
        """
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(create_tables_sql)
            logger.info("Zeek tables ensured in PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def parse_zeek_json_line(self, line: str) -> Optional[Dict]:
        """Parse a single line of Zeek JSON log format."""
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None
    
    async def insert_zeek_event(self, event_data: Dict) -> bool:
        """Insert generic Zeek event into database."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO zeek_events 
                    (log_type, source_ip, dest_ip, source_port, dest_port, protocol, 
                     event_text, severity, raw_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    event_data.get('log_type', 'unknown'),
                    event_data.get('source_ip'),
                    event_data.get('dest_ip'),
                    event_data.get('source_port'),
                    event_data.get('dest_port'),
                    event_data.get('protocol'),
                    event_data.get('event_text', ''),
                    event_data.get('severity', 'info'),
                    json.dumps(event_data)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to insert event: {e}")
            return False
    
    async def insert_connection(self, conn_data: Dict) -> bool:
        """Insert Zeek connection event into database."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            raw_json = json.dumps(conn_data)
            
            logger.debug(f"Inserting connection: {conn_data.get('uid')}")
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO zeek_conn (log)
                    VALUES ($1)
                    """,
                    raw_json
                )
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to insert connection: {e}")
            return False
    
    async def insert_dns_event(self, dns_data: Dict) -> bool:
        """Insert Zeek DNS event into database."""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        try:
            async with self.pool.acquire() as conn:
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
                    str(dns_data.get("qtype", "")),
                    str(dns_data.get("rcode", "")),
                    dns_data.get("answers", []),
                    json.dumps(dns_data)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to insert DNS event: {e}")
            return False
    
    async def parse_and_ingest_log_content(self, 
                                          log_content: str,
                                          log_type: str) -> Tuple[int, int]:
        """
        Parse Zeek log content and ingest into database.
        
        Returns: (lines_processed, lines_inserted)
        """
        lines_processed = 0
        lines_inserted = 0
        
        try:
            for line in log_content.split('\n'):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                lines_processed += 1
                
                # Parse JSON line
                parsed = self.parse_zeek_json_line(line)
                if not parsed:
                    continue
                
                # Route to appropriate insert function based on log type
                success = False
                if log_type == 'conn.log':
                    success = await self.insert_connection(parsed)
                elif log_type == 'dns.log':
                    success = await self.insert_dns_event(parsed)
                else:
                    # Generic event
                    parsed['log_type'] = log_type.replace('.log', '')
                    success = await self.insert_zeek_event(parsed)
                
                if success:
                    lines_inserted += 1
            
            logger.info(f"Processed {log_type}: {lines_processed} lines, {lines_inserted} inserted")
            return lines_processed, lines_inserted
        
        except Exception as e:
            logger.error(f"Error parsing and ingesting {log_type}: {e}")
            return lines_processed, lines_inserted
