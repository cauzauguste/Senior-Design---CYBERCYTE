import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO incidents (threat_type, severity, source_ip, dest_ip, details, gemini_analysis, openai_analysis)
        VALUES (:threat_type, :severity, :source_ip, :dest_ip, :details, :gemini_analysis, :openai_analysis)
    """), {
        'threat_type': 'Test Threat',
        'severity': 'medium',
        'source_ip': '192.168.1.1',
        'dest_ip': '10.0.0.1',
        'details': json.dumps({'description': 'This is a test threat description'}),
        'gemini_analysis': 'Gemini analysis: This appears to be a test threat. Mitigation: Monitor closely.',
        'openai_analysis': 'OpenAI analysis: Test incident detected. Suggest blocking the IP.'
    })
    conn.commit()

print("Test incident inserted.")