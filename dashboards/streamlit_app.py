import streamlit as st
<<<<<<< HEAD
import pandas as pd
import sys
import os

# ✅ Add the project root (one level up) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import get_db
from app.models import RawLog

st.title("CYBERCYTE Threat Dashboard")

# Get a database session
db = next(get_db())

# Query last 20 events
events = db.query(RawLog).order_by(RawLog.id.desc()).limit(20).all()

# Close session
db.close()

# Display as table
df = pd.DataFrame([{
    "ID": e.id,
    "Host": e.host_id,
    "Source IP": e.src_ip,
    "Type": e.event_type,
    "Processed": e.processed,
    "Timestamp": e.timestamp
} for e in events])

st.table(df)
=======
import requests
import pandas as pd

API_URL = "https://localhost:8443/telemetry"

st.title("Gemini Threat Dashboard")

if st.button("Load Latest Telemetry"):
    resp = requests.get(API_URL, verify="certificates/ca-cert.pem")
    df = pd.DataFrame(resp.json())
    st.dataframe(df)
    st.line_chart(df["size"])
>>>>>>> 5a941a1959ecf6e3d917b785491382061f7ea8a4
