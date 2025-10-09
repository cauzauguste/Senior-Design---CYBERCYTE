from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter(prefix="/events", tags=["Events"])

@router.post("/", response_model=schemas.EventCreate)
def create_event(event: schemas.EventCreate, db: Session = Depends(database.get_db)):
    new_event = models.Event(**event.dict())
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.get("/")
def list_events(db: Session = Depends(database.get_db)):
    return db.query(models.Event).all()
