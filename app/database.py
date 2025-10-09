from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

<<<<<<< HEAD
# Supabase/Postgres connection
=======
>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4
DATABASE_URL = "postgresql://postgres:pass@localhost:5432/cybercyte_db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
<<<<<<< HEAD
=======

>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4
Base = declarative_base()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
