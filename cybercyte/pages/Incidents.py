import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('../.env')

st.title("🚨 Incident Logs 🚨 ")

@st.cache_data
def load_data():
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, threat_type as event_type, severity, source_ip, dest_ip, 
                   details, timestamp, gemini_analysis, openai_analysis, status
            FROM incidents 
            ORDER BY timestamp DESC
        """))
        rows = result.fetchall()
        data = [row._asdict() for row in rows]
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

df = load_data()

# Filters
event_type = st.selectbox("Filter by Event Type", options=["All"] + df["event_type"].unique().tolist())
if event_type != "All":
    df = df[df["event_type"] == event_type]

# Show table
st.dataframe(
    df[['timestamp', 'event_type', 'severity', 'source_ip', 'dest_ip', 'status']].sort_values("timestamp", ascending=False), 
    use_container_width=True
)

# Show details for each incident
st.subheader("Incident Details")
for idx, row in df.iterrows():
    with st.expander(f"{row['event_type']} - {row['timestamp']} - {row['severity']}"):
        st.write(f"**Source IP:** {row.get('source_ip', 'N/A')}")
        st.write(f"**Destination IP:** {row.get('dest_ip', 'N/A')}")
        st.write(f"**Status:** {row.get('status', 'N/A')}")
        st.write(f"**Details:** {row.get('details', 'N/A')}")
        st.write(f"**Gemini Analysis:** {row.get('gemini_analysis', 'N/A')}")
        st.write(f"**OpenAI Analysis:** {row.get('openai_analysis', 'N/A')}")
