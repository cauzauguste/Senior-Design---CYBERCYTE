<<<<<<< HEAD
from app.database import Base, engine
from app.models import Event, RawLog
=======
# create_tables.py
from app.database import Base, engine
from app.models import Event
>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
