from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import supabase_client
import os

DB_BACKEND = os.getenv("DB_BACKEND", "supabase")  # or "postgres"

class DBAdapter:
    def __init__(self, backend="supabase"):
        self.backend = backend
        if backend == "supabase":
            if not supabase_client:
                raise ValueError("Supabase backend requires app.supabase_client setup")
            self.client = supabase_client
        elif backend == "postgres":
            self.engine = create_engine(os.getenv("DATABASE_URL"))
            self.SessionLocal = sessionmaker(bind=self.engine)
        else:
            raise ValueError("Unsupported backend specified")

    def log_event(self, event_data):
        if self.backend == "supabase":
            response = self.client.table("events").insert(event_data).execute()
            return response
        elif self.backend == "postgres":
            session = self.SessionLocal()
            try:
                from app.models import Event
                new_event = Event(**event_data)
                session.add(new_event)
                session.commit()
                return new_event
            finally:
                session.close()
