# backend/app/main.py

from fastapi import FastAPI

# Import routers (all fixed)
from backend.app.routes.auth import router as auth_router
from backend.app.routes.dashboard import router as dashboard_router
from backend.app.routes.events import router as events_router
from backend.app.routes.monitor_dash import router as monitor_router
from backend.app.routes.pcap_api import router as pcap_router
from backend.app.routes.telemetry import router as telemetry_router
from backend.app.routes.threats import router as threats_router

app = FastAPI(title="Cybercyte Backend")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

# Register routers with proper prefixes
app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(events_router, prefix="/events", tags=["Events"])
app.include_router(monitor_router, prefix="/monitor", tags=["Monitor"])
app.include_router(pcap_router, prefix="/pcap", tags=["PCAP"])
app.include_router(telemetry_router, prefix="/telemetry", tags=["Telemetry"])
app.include_router(threats_router, prefix="/threats", tags=["Threats"])
