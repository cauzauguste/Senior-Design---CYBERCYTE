from app.database import Base, engine
from app.models import Event, RawLog

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
