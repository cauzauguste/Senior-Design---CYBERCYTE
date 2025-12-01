from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/")
def auth_root():
    return {"msg": "auth ok"}
