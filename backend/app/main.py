# backend/app/main.py

from fastapi import FastAPI
import os
import logging
from asyncio import to_thread
from sqlalchemy import text

# Import database engine for startup checks
from backend.app import database

# Import routers (all fixed)
from backend.app.routes.auth import router as auth_router
from backend.app.routes.dashboard import router as dashboard_router
from backend.app.routes.events import router as events_router
from backend.app.routes.monitor_dash import router as monitor_router
from backend.app.routes.pcap_api import router as pcap_router
from backend.app.routes.telemetry import router as telemetry_router
from backend.app.routes.threats import router as threats_router
from backend.app.routes.zeek import router as zeek_router
from backend.app.routes.zeek_remote import router as zeek_remote_router

app = FastAPI(title="Cybercyte Backend")

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup_event():
    """Startup event: check DB connectivity and log the DB URL in use."""
    db_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    logger.info(f"Database URL in use: {db_url}")

    def _test_conn():
        conn = database.engine.connect()
        try:
            conn.execute(text("SELECT 1"))
        finally:
            conn.close()

    try:
        await to_thread(_test_conn)
        logger.info("Database connectivity test passed")
    except Exception as e:
        logger.error(f"Database connectivity test failed: {e}")


@app.on_event("shutdown")
def shutdown_event():
    try:
        database.engine.dispose()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


# System diagnostics endpoint
@app.get("/diagnostics")
async def diagnostics():
    """Report system info, Python packages, and dependencies."""
    import sys
    import platform
    import subprocess
    
    diag = {
        "os": platform.system(),
        "os_version": platform.release(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_executable": sys.executable,
        "platform": platform.platform(),
    }
    
    # Check for key binaries
    key_tools = ["psql", "pg_isready", "git", "nc", "curl"]
    tools_status = {}
    for tool in key_tools:
        try:
            result = subprocess.run(
                ["which", tool], 
                capture_output=True, 
                text=True, 
                timeout=2
            )
            tools_status[tool] = "installed" if result.returncode == 0 else "not found"
        except Exception as e:
            tools_status[tool] = f"error: {str(e)}"
    
    diag["tools"] = tools_status
    
    # Check key Python packages
    key_packages = [
        "fastapi", "uvicorn", "sqlalchemy", "psycopg2", "asyncpg",
        "pydantic", "scapy", "python-multipart", "aiokafka", "paramiko"
    ]
    packages_status = {}
    for pkg in key_packages:
        try:
            __import__(pkg.replace("-", "_"))
            packages_status[pkg] = "installed"
        except ImportError:
            packages_status[pkg] = "not installed"
    
    diag["python_packages"] = packages_status
    
    # Database connectivity
    try:
        conn = database.engine.connect()
        conn.execute(text("SELECT 1"))
        conn.close()
        diag["database"] = "connected"
    except Exception as e:
        diag["database"] = f"error: {str(e)}"
    
    return diag

# Register routers with proper prefixes
# Register routers (router modules define their own prefixes/tags)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(events_router)
app.include_router(monitor_router)
app.include_router(pcap_router)
app.include_router(telemetry_router)
app.include_router(threats_router)
app.include_router(zeek_router)
app.include_router(zeek_remote_router)

