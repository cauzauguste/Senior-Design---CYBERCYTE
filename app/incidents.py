# incidents.py
import streamlit as st
import pandas as pd
from datetime import datetime
from app.db_adapter import DBAdapter

# Choose backend: "supabase" or "sqlalchemy"
DB_BACKEND = "supabase"
db_adapter = DBAdapter(backend=DB_BACKEND)

st.set_page_config(page_title="CYBERCYTE Live Incidents", layout="wide")
st.title("CYBERCYTE - Live Threat Incidents")

# -------------------------
# Fetch logs from backend
# -------------------------
def fetch_logs(limit=50):
    if DB_BACKEND == "supabase":
        try:
            data = db_adapter.db_adapter.supabase.table("raw_logs").select("*").order("timestamp", desc=True).limit(limit).execute().data
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch from Supabase: {e}")
            return pd.DataFrame()
    else:
        # SQLAlchemy
        db = db_adapter.db_adapter.SessionLocal()
        try:
            rows = db.query(db_adapter.db_adapter.RawLog).order_by(db_adapter.db_adapter.RawLog.timestamp.desc()).limit(limit).all()
            return pd.DataFrame([{
                "host_id": r.host_id,
                "src_ip": r.src_ip,
                "dst_ip": r.dst_ip,
                "event_type": r.event_type,
                "event_text": r.event_text,
                "bytes_sent": r.bytes_sent,
                "bytes_received": r.bytes_received,
                "timestamp": r.timestamp,
                "processed": r.processed
            } for r in rows])
        finally:
            db.close()

# -------------------------
# Main dashboard
# -------------------------
st.sidebar.header("Settings")
limit = st.sidebar.slider("Number of events to show", min_value=10, max_value=200, value=50, step=10)
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", min_value=5, max_value=60, value=10, step=5)

# Auto-refresh
logs = fetch_logs(limit)
if not logs.empty:
    logs["timestamp"] = pd.to_datetime(logs["timestamp"])
    st.dataframe(logs.sort_values("timestamp", ascending=False))
else:
    st.warning("No logs found!")

st.experimental_rerun()
