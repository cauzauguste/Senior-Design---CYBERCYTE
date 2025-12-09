import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text

# Same as database.py
DATABASE_URL = os.getenv(
    "POSTGRES_URL",
    os.getenv("DATABASE_URL", "postgresql://postgres:pass@localhost:5432/cybercyte_db")
)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM incidents;'))
    count = result.fetchone()[0]
    print(f'Number of incidents: {count}')
    if count > 0:
        result = conn.execute(text('SELECT threat_type, severity, description, source_ip, gemini_analysis, openai_analysis FROM incidents ORDER BY timestamp DESC LIMIT 3;'))
        for row in result.fetchall():
            print(row._asdict())