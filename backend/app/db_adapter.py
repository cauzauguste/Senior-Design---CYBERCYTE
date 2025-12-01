import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_BACKEND = os.getenv("DB_BACKEND", "postgres")


class DBAdapter:
    def __init__(self, backend: str | None = None):
        self.backend = backend or DB_BACKEND

        if self.backend == "supabase":
            # Import only when needed, so missing Supabase lib doesn't break Postgres mode
            from .supabase_client import SupabaseClient  # type: ignore

            self.client = SupabaseClient().client

        elif self.backend == "postgres":
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                raise ValueError("DATABASE_URL environment variable is not set")

            self.engine = create_engine(database_url)
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        else:
            raise ValueError(f"Unsupported backend specified: {self.backend}")

    def log_event(self, event_data: dict):
        if self.backend == "supabase":
            response = self.client.table("events").insert(event_data).execute()
            return response

        elif self.backend == "postgres":
            from .models import Event

            session = self.SessionLocal()
            try:
                new_event = Event(**event_data)
                session.add(new_event)
                session.commit()
                session.refresh(new_event)
                return new_event
            finally:
                session.close()
