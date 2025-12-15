import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# -------------------------------------------
# PAGE CONFIG
# -------------------------------------------
st.set_page_config(page_title="Incident Logs", layout="wide")
st.title("🚨 Incident Logs — Full Event History")


# -------------------------------------------
# LOAD DATA FROM SQLITE DB
# -------------------------------------------
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect("threat_events.db")

        # Check common event table names
        possible_tables = ["security_events", "events", "threat_events", "logs"]
        df = None

        for table in possible_tables:
            try:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                print(f"Loaded table: {table}")
                break
            except:
                continue

        conn.close()

        if df is None:
            st.error("⚠️ Could not find an events table inside threat_events.db")
            return pd.DataFrame()

        # Convert timestamp fields automatically
        for col in df.columns:
            if "time" in col.lower() or "date" in col.lower():
                df[col] = pd.to_datetime(df[col], errors="coerce")

        # Add DATE column if missing
        if "DATE" not in df.columns and "timestamp" in df.columns:
            df["DATE"] = df["timestamp"].dt.date

        return df

    except Exception as e:
        st.error(f"❌ Error loading database: {e}")
        return pd.DataFrame()


df = load_data()

if df.empty:
    st.stop()


# -------------------------------------------
# FILTERS
# -------------------------------------------
st.sidebar.header("🔎 Filters")

# Event Type Filter
if "event_type" in df.columns:
    event_type = st.sidebar.selectbox(
        "Filter by Event Type",
        options=["All"] + sorted(df["event_type"].dropna().unique().tolist())
    )
else:
    event_type = "All"

if event_type != "All" and "event_type" in df.columns:
    df = df[df["event_type"] == event_type]

# Keyword Search
search = st.sidebar.text_input("Search Description / Host / IP")

if search:
    df = df[
        df.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False))
    ]


# Date Range Filter
if "DATE" in df.columns:
    min_date = df["DATE"].min()
    max_date = df["DATE"].max()

    start_date = st.sidebar.date_input("Start Date", min_value=min_date, max_value=max_date, value=min_date)
    end_date = st.sidebar.date_input("End Date", min_value=min_date, max_value=max_date, value=max_date)

    df = df[(df["DATE"] >= start_date) & (df["DATE"] <= end_date)]


# -------------------------------------------
# INCIDENT TABLE
# -------------------------------------------
st.subheader("📋 All Logged Incidents")

# Pick the most relevant available columns
priority_columns = [
    "timestamp",
    "event_type",
    "description",
    "infected_host",
    "remote_ip",
    "source_ip",
    "destination_ip",
    "action_status",
]

available_columns = [c for c in priority_columns if c in df.columns]

if not available_columns:
    available_columns = df.columns  # fallback

st.dataframe(
    df.sort_values(df.columns[0], ascending=False)[available_columns],
    use_container_width=True
)

st.success("✅ Incident log loaded successfully.")
