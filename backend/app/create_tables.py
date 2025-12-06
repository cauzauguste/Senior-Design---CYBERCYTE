from app.database import Base, engine
import app.models  # Ensure all models are imported so metadata includes them

Base.metadata.create_all(bind=engine)
print("Tables created successfully!")
