from fastapi import APIRouter
from backend.app.detector import LLMEvaluator
from backend.app.database import SessionLocal
from backend.app.models import Incident
from backend.app.threat_detector import router as threat_detector_router

router = APIRouter(prefix="/threats", tags=["Threats"])

# Include the threat detector router
router.include_router(threat_detector_router)

@router.get("/raw_logs")
def get_logs():
    return {"msg": "threat logs test"}

@router.get("/")
def threats_root():
    return {"msg": "threats root"}

@router.post("/detect")
def detect_threats():
    """Run threat detection and return alerts."""
    evaluator = LLMEvaluator()
    alerts = evaluator.run_all_detections()
    return {"alerts": alerts}

@router.get("/incidents")
def get_incidents(limit: int = 50):
    """Get detected incidents."""
    db = SessionLocal()
    try:
        incidents = db.query(Incident).order_by(Incident.timestamp.desc()).limit(limit).all()
        return {"incidents": [
            {
                "id": i.id,
                "threat_type": i.threat_type,
                "severity": i.severity,
                "source_ip": i.source_ip,
                "dest_ip": i.dest_ip,
                "details": i.details,
                "timestamp": i.timestamp,
                "status": i.status
            } for i in incidents
        ]}
    finally:
        db.close()
