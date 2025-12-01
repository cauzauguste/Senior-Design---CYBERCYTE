from fastapi import APIRouter

router = APIRouter(prefix="/threats", tags=["Threats"])

@router.get("/raw_logs")
def get_logs():
    return {"msg": "threat logs test"}

@router.get("/")
def threats_root():
    return {"msg": "threats root"}
