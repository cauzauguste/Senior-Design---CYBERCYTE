# detectpr_prototype_fastapi.py
from fastapi import FastAPI
from pydantic import BaseModel
from app.threat_manager import log_threat_to_db
from fastapi import status
from dotenv import load_dotenv

# Load environment variables from conf.env
load_dotenv('conf.env')

app = FastAPI()

class GenerateEventRequest(BaseModel):
    host_id: str
    src_ip: str
    event_type: str
    event_text: str

@app.post("/generate_event")
def generate_event(event: GenerateEventRequest):
    logged_event = log_threat_to_db(
        host_id=event.host_id,
        src_ip=event.src_ip,
        event_type=event.event_type,
        event_text=event.event_text
    )
    return {"status": "ok", "event_id": logged_event.id}
# --- Health endpoint for CI ---

@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok"}
