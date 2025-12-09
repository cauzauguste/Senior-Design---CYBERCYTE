import asyncio
from backend.app.threat_detector import run_threat_detection_once

if __name__ == "__main__":
    asyncio.run(run_threat_detection_once())