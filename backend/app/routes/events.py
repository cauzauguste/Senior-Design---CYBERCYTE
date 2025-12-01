from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(prefix="/events", tags=["Events"])

@router.get("/")
def list_events(db: Session = Depends(database.get_db)):
    return db.query(models.Event).all()

