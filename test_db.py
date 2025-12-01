from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://postgres:pass@34.132.194.35:5432/postgres"

engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT NOW();"))
        for row in result:
            print("Connected successfully. Current time:", row[0])
except Exception as e:
    print("❌ Connection failed:", e)
