from fastapi import APIRouter

router = APIRouter()

@router.get("/raw_logs")
def get_logs():
    return {"msg": "test logs"}
