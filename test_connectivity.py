#!/usr/bin/env python3
"""
Cybercyte VM Connectivity Test Script

Tests connectivity between:
- FastAPI VM (34.170.121.14)
- Zeek VM (34.63.246.217)
- PostgreSQL VM (34.132.194.35)

Usage:
    python3 test_connectivity.py
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
import paramiko
import asyncpg
import ssl

load_dotenv()

# Configuration from environment
ZEEK_REMOTE_HOST = os.getenv("ZEEK_REMOTE_HOST", "35.222.249.202")
ZEEK_REMOTE_PORT = int(os.getenv("ZEEK_REMOTE_PORT", "22"))
ZEEK_REMOTE_USER = os.getenv("ZEEK_REMOTE_USER", "zauguste52")
ZEEK_REMOTE_PATH = os.getenv("ZEEK_REMOTE_PATH", "/opt/zeek/logs/current")
ZEEK_SSH_KEY = os.getenv("ZEEK_SSH_KEY", None)
ZEEK_SSH_PASSWORD = os.getenv("ZEEK_SSH_PASSWORD", None)

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db")
POSTGRES_CA_FILE = os.getenv("POSTGRES_CA_FILE", None)

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str, indent: int = 0):
    """Print info message."""
    prefix = "  " * indent
    print(f"{prefix}{BLUE}ℹ {text}{RESET}")


async def test_zeek_ssh_connection() -> Dict[str, Any]:
    """Test SSH connection to Zeek VM."""
    print_header("Testing Zeek VM SSH Connection")
    print_info(f"Target: {ZEEK_REMOTE_USER}@{ZEEK_REMOTE_HOST}:{ZEEK_REMOTE_PORT}")
    print_info(f"Remote path: {ZEEK_REMOTE_PATH}")
    
    result = {
        "host": ZEEK_REMOTE_HOST,
        "port": ZEEK_REMOTE_PORT,
        "status": "failed",
        "details": {}
    }
    
    transport = None
    sftp = None
    
    try:
        # Create transport
        transport = paramiko.Transport((ZEEK_REMOTE_HOST, ZEEK_REMOTE_PORT))
        print_info("Transport created, attempting authentication...")
        
        # Authenticate
        if ZEEK_SSH_KEY and os.path.exists(ZEEK_SSH_KEY):
            print_info(f"Using SSH key: {ZEEK_SSH_KEY}", 1)
            # Try different key types
            key = None
            try:
                key = paramiko.RSAKey.from_private_key_file(ZEEK_SSH_KEY)
            except paramiko.ssh_exception.SSHException:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(ZEEK_SSH_KEY)
                except paramiko.ssh_exception.SSHException:
                    try:
                        key = paramiko.ECDSAKey.from_private_key_file(ZEEK_SSH_KEY)
                    except paramiko.ssh_exception.SSHException:
                        try:
                            key = paramiko.DSSKey.from_private_key_file(ZEEK_SSH_KEY)
                        except paramiko.ssh_exception.SSHException:
                            raise Exception("Unsupported SSH key type")
            transport.connect(username=ZEEK_REMOTE_USER, pkey=key)
        else:
            print_info(f"Using SSH password authentication", 1)
            transport.connect(username=ZEEK_REMOTE_USER, password=ZEEK_SSH_PASSWORD or "")
        
        print_success("SSH authentication successful")
        result["status"] = "connected"
        
        # Try SFTP
        sftp = paramiko.SFTPClient.from_transport(transport)
        print_info("SFTP channel opened")
        
        # List files in remote path
        try:
            files = sftp.listdir_attr(ZEEK_REMOTE_PATH)
            log_files = [f.filename for f in files if f.filename.endswith('.log')]
            
            result["details"]["remote_path_accessible"] = True
            result["details"]["total_files_in_path"] = len(files)
            result["details"]["zeek_log_files"] = log_files
            result["details"]["log_file_count"] = len(log_files)
            
            print_success(f"Remote path accessible")
            print_info(f"Found {len(log_files)} Zeek log files", 1)
            
            if log_files:
                print_info("Sample log files:", 1)
                for f in log_files[:5]:
                    print_info(f"- {f}", 2)
                if len(log_files) > 5:
                    print_info(f"... and {len(log_files) - 5} more", 2)
        
        except Exception as e:
            print_warning(f"Could not list remote path: {e}")
            result["details"]["remote_path_accessible"] = False
            result["details"]["error"] = str(e)
    
    except paramiko.AuthenticationException as e:
        print_error(f"SSH authentication failed: {e}")
        result["details"]["error"] = f"Authentication failed: {e}"
    
    except paramiko.SSHException as e:
        print_error(f"SSH connection error: {e}")
        result["details"]["error"] = f"SSH error: {e}"
    
    except Exception as e:
        print_error(f"Connection failed: {e}")
        result["details"]["error"] = str(e)
    
    finally:
        try:
            if sftp:
                sftp.close()
            if transport:
                transport.close()
        except Exception:
            pass
    
    return result


async def test_postgres_connection() -> Dict[str, Any]:
    """Test PostgreSQL connection."""
    print_header("Testing PostgreSQL VM Connection")
    
    # Parse URL
    try:
        # postgresql://postgres:pass@34.132.194.35:5432/cybercyte_db
        parts = POSTGRES_URL.replace("postgresql://", "").split("/")
        db_name = parts[-1]
        
        conn_info = parts[0].split("@")
        user_pass = conn_info[0].split(":")
        user = user_pass[0]
        
        host_port = conn_info[1].split(":")
        host = host_port[0]
        port = int(host_port[1])
        
        print_info(f"Target: {user}@{host}:{port}/{db_name}")
    except Exception as e:
        print_error(f"Could not parse PostgreSQL URL: {e}")
        return {
            "host": "unknown",
            "port": 5432,
            "status": "failed",
            "details": {"error": f"URL parsing failed: {e}"}
        }
    
    result = {
        "host": host,
        "port": port,
        "database": db_name,
        "status": "failed",
        "details": {}
    }
    
    pool = None
    
    try:
        # Create connection
        connect_args = {}
        if POSTGRES_CA_FILE and os.path.exists(POSTGRES_CA_FILE):
            connect_args['ssl'] = ssl.create_default_context(cafile=POSTGRES_CA_FILE)
        
        print_info("Creating connection pool...")
        pool = await asyncpg.create_pool(
            POSTGRES_URL,
            min_size=1,
            max_size=1,
            **connect_args
        )
        
        print_success("Connection pool created")
        
        # Test query
        async with pool.acquire() as conn:
            # Get version
            version = await conn.fetchval("SELECT version()")
            print_success(f"PostgreSQL connected: {version[:60]}...")
            result["details"]["version"] = version
            
            # Check if Zeek tables exist
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name LIKE 'zeek_%'
            """
            tables = await conn.fetch(tables_query)
            zeek_tables = [t['table_name'] for t in tables]
            
            result["details"]["zeek_tables"] = zeek_tables
            result["details"]["zeek_tables_count"] = len(zeek_tables)
            
            if zeek_tables:
                print_success(f"Found {len(zeek_tables)} Zeek tables:")
                for table in zeek_tables:
                    print_info(f"- {table}", 1)
            else:
                print_warning("No Zeek tables found - may need to initialize schema")
            
            # Get table row counts
            if zeek_tables:
                print_info("Row counts:", 1)
                for table in zeek_tables[:3]:  # Show first 3
                    try:
                        count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                        print_info(f"- {table}: {count} rows", 2)
                    except Exception as e:
                        print_warning(f"Could not count {table}: {e}", 2)
        
        result["status"] = "connected"
        print_success("PostgreSQL connectivity verified")
    
    except asyncpg.PostgresError as e:
        print_error(f"PostgreSQL error: {e}")
        result["details"]["error"] = str(e)
    
    except Exception as e:
        print_error(f"Connection failed: {e}")
        result["details"]["error"] = str(e)
    
    finally:
        if pool:
            await pool.close()
    
    return result


async def test_fastapi_local() -> Dict[str, Any]:
    """Test local FastAPI setup."""
    print_header("Testing Local FastAPI Setup")
    
    result = {
        "status": "ok",
        "details": {}
    }
    
    # Check environment variables
    print_info("Environment variables:")
    env_vars = {
        "ZEEK_REMOTE_HOST": ZEEK_REMOTE_HOST,
        "ZEEK_REMOTE_USER": ZEEK_REMOTE_USER,
        "ZEEK_REMOTE_PATH": ZEEK_REMOTE_PATH,
        "POSTGRES_URL": POSTGRES_URL.replace("pass", "****"),  # Mask password
        "ZEEK_SSH_KEY": ZEEK_SSH_KEY or "Not set (using password auth)"
    }
    
    for key, value in env_vars.items():
        print_info(f"{key}={value}", 1)
        result["details"][key] = value
    
    # Check Python packages
    print_info("\nChecking Python packages:")
    packages = ["paramiko", "asyncpg", "fastapi", "uvicorn", "sqlalchemy"]
    
    for pkg in packages:
        try:
            __import__(pkg)
            print_success(f"{pkg} installed", )
            result["details"][f"pkg_{pkg}"] = "installed"
        except ImportError:
            print_error(f"{pkg} NOT installed")
            result["details"][f"pkg_{pkg}"] = "missing"
    
    return result


async def main():
    """Run all connectivity tests."""
    print(f"\n{BOLD}{BLUE}")
    print("=" * 70)
    print("CYBERCYTE VM CONNECTIVITY DIAGNOSTIC")
    print("=" * 70)
    print(f"Test started: {datetime.now().isoformat()}")
    print(f"{RESET}\n")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "fastapi": await test_fastapi_local(),
        "zeek_vm": await test_zeek_ssh_connection(),
        "postgres_vm": await test_postgres_connection(),
    }
    
    # Summary
    print_header("Connectivity Summary")
    
    all_ok = all(r["status"] in ["connected", "ok"] for r in results.values() if isinstance(r, dict) and "status" in r)
    
    print(f"FastAPI local setup: {GREEN if results['fastapi']['status'] == 'ok' else RED}{results['fastapi']['status']}{RESET}")
    print(f"Zeek VM ({ZEEK_REMOTE_HOST}): {GREEN if results['zeek_vm']['status'] == 'connected' else RED}{results['zeek_vm']['status']}{RESET}")
    print(f"PostgreSQL VM (34.132.194.35): {GREEN if results['postgres_vm']['status'] == 'connected' else RED}{results['postgres_vm']['status']}{RESET}")
    
    print()
    if all_ok:
        print_success("All connectivity tests PASSED - System is ready!")
    else:
        print_warning("Some connectivity tests FAILED - See details above")
    
    # Save results to file
    results_file = "connectivity_test_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print_info(f"\nResults saved to: {results_file}")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
