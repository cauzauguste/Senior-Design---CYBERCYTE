import streamlit as st
import pandas as pd
import altair as alt
import sqlite3
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="CyberCyte Dashboard", layout="wide")

BACKEND_URL = "http://127.0.0.1:8000/get_latest_threats"

# ============================================================
# Helper: Remove Duplicate Columns
# ============================================================
def dedupe(df):
    return df.loc[:, ~df.columns.duplicated()]


# ============================================================
# LOAD FROM BACKEND
# ============================================================
@st.cache_data
def load_from_backend():
    try:
        resp = requests.get(BACKEND_URL, timeout=5)
        resp.raise_for_status()
        df = pd.DataFrame(resp.json())

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"])
            df["DATE"] = df["timestamp"].dt.date

        return dedupe(df)
    except Exception:
        return pd.DataFrame()


# ============================================================
# LOAD FROM SQLITE (FALLBACK)
# ============================================================
@st.cache_data
def load_from_sqlite():
    try:
        conn = sqlite3.connect("threat_events.db")
        events_df = pd.read_sql("SELECT * FROM events", conn)

        try:
            threats_df = pd.read_sql("SELECT * FROM threat_detections", conn)
        except Exception:
            threats_df = pd.DataFrame()

        conn.close()

        if "timestamp" not in events_df.columns:
            return pd.DataFrame()

        events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], errors="coerce")
        events_df = events_df.dropna(subset=["timestamp"])
        events_df["DATE"] = events_df["timestamp"].dt.date

        if not threats_df.empty:
            merged = events_df.merge(
                threats_df,
                how="left",
                left_on="id",
                right_on="event_id",
                suffixes=("", "_threat"),
            )
            return dedupe(merged)

        return dedupe(events_df)

    except Exception:
        return pd.DataFrame()


# ============================================================
# UNIFIED LOADER
# ============================================================
def load_data():
    df = load_from_backend()
    if df.empty:
        df = load_from_sqlite()
    return dedupe(df)


df = load_data()

if df.empty:
    st.error("No data available from backend or SQLite.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"])
df["DATE"] = df["timestamp"].dt.date
df = dedupe(df)


# ============================================================
# SIDEBAR FILTERS
# ============================================================
with st.sidebar:
    st.title("CyberCyte Dashboard Filters")

    min_date = df["DATE"].min()
    max_date = df["DATE"].max()

    start_default = max(max_date - timedelta(days=30), min_date)

    start_date = st.date_input(
        "Start Date", start_default, min_value=min_date, max_value=max_date
    )
    end_date = st.date_input(
        "End Date", max_date, min_value=min_date, max_value=max_date
    )


filtered_df = df[(df["DATE"] >= start_date) & (df["DATE"] <= end_date)]
filtered_df = dedupe(filtered_df)


# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Analytics",
    "📁 Event Types",
    "🤖 Gemini Confidence",
    "📡 Bryson Clients"
])


# ============================================================
# TAB 1 — ANALYTICS
# ============================================================
with tab1:
    st.header("📊 Events Over Time")

    events_over_time = (
        filtered_df.groupby(filtered_df["timestamp"].dt.date)
        .size()
        .reset_index(name="event_count")
    )
    events_over_time.columns = ["date", "event_count"]
    events_over_time = dedupe(events_over_time)

    if not events_over_time.empty:
        events_over_time["date"] = pd.to_datetime(events_over_time["date"])
        chart = alt.Chart(events_over_time).mark_area(color="#29b5e8").encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("event_count:Q", title="Events"),
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No events in this date range.")

    st.subheader("📄 Recent Incidents")
    cols = [
        c for c in [
            "timestamp", "source", "event_type",
            "anomaly_score", "gemini_confidence",
            "mitigation_suggestion", "raw_data"
        ] if c in filtered_df.columns
    ]
    st.dataframe(
        filtered_df.sort_values("timestamp", ascending=False)[cols].head(25),
        use_container_width=True
    )


# ============================================================
# TAB 2 — EVENT TYPE BREAKDOWN
# ============================================================
with tab2:
    st.header("📁 Event Type Breakdown")

    if "event_type" in filtered_df.columns:
        type_df = (
            filtered_df["event_type"]
            .value_counts()
            .reset_index()
        )
        type_df.columns = ["event_type", "count"]
        type_df = dedupe(type_df)

        if not type_df.empty:
            bar = alt.Chart(type_df).mark_bar().encode(
                x="event_type:N",
                y="count:Q",
                color="event_type:N",
            )
            st.altair_chart(bar, use_container_width=True)
        else:
            st.info("No event type data.")
    else:
        st.warning("No event_type column found.")


# ============================================================
# TAB 3 — GEMINI CONFIDENCE
# ============================================================
with tab3:
    st.header("🤖 Gemini Confidence Over Time")

    if "gemini_confidence" in filtered_df.columns:
        conf_df = filtered_df[["timestamp", "gemini_confidence"]].dropna()
        conf_df = dedupe(conf_df)

        if not conf_df.empty:
            conf_chart = alt.Chart(conf_df).mark_line(color="#FF5C5C").encode(
                x="timestamp:T",
                y="gemini_confidence:Q"
            )
            st.altair_chart(conf_chart, use_container_width=True)
        else:
            st.info("No Gemini data available.")
    else:
        st.warning("No Gemini confidence field found.")


# ============================================================
# TAB 4 — BRYSON CLIENTS
# ============================================================
with tab4:
    st.header("📡 Clients (Bryson Backend)")

    BRYSON_CLIENTS_URL = "http://34.172.159.200:8000/api/clients/status"
    BRYSON_API_KEY = "a_very_strong_secret"

    def fetch_clients_from_bryson():
        try:
            r = requests.get(
                BRYSON_CLIENTS_URL,
                headers={"X-API-Key": BRYSON_API_KEY},
                timeout=10
            )
            r.raise_for_status()
            return pd.DataFrame(r.json())
        except Exception as e:
            st.error(f"Could not connect to Bryson backend: {e}")
            return pd.DataFrame()

    client_df = fetch_clients_from_bryson()

    if client_df.empty:
        st.info("No client data reported.")
    else:
        client_df = dedupe(client_df)
        st.dataframe(client_df, use_container_width=True)
        st.success(f"Loaded {len(client_df)} clients from Bryson backend.")

