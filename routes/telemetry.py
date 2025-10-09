from fastapi import APIRouter
from app.database import db

router = APIRouter()

@router.get("/")
async def get_latest_telemetry(limit: int = 100):
    cursor = db.telemetry.find().sort("timestamp", -1).limit(limit)
    results = await cursor.to_list(length=limit)
    return results

@router.get("/count")
async def telemetry_count():
    count = await db.telemetry.count_documents({})
    return {"count": count}
