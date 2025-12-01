import streamlit as st
import pandas as pd
import altair as alt
import sqlite3
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="CyberCyte Dashboard", layout="wide")

BACKEND_URL = "http://127.0.0.1:8000/get_latest_threats"  # FastAPI endpoint

# =====================================================
# LOAD FROM BACKEND (PRIMARY PATH)
# =====================================================
@st.cache_data
def load_from_backend():
    try:
        resp = requests.get(BACKEND_URL, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data)

            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.dropna(subset=["timestamp"])
                df["DATE"] = df["timestamp"].dt.date

            return df
        else:
            st.warning(f"Backend returned status {resp.status_code}, using SQLite fallback.")
            return pd.DataFrame()
    except Exception as e:
        st.warning(f"Could not reach backend: {e}. Using SQLite fallback.")
        return pd.DataFrame()


# =====================================================
# LOAD FROM SQLITE (FALLBACK)
# =====================================================
@st.cache_data
def load_from_sqlite():
    try:
        conn = sqlite3.connect("threat_events.db")
        events_df = pd.read_sql("SELECT * FROM events", conn)
        # threat_detections might be used for extra fields
        try:
            threats_df = pd.read_sql("SELECT * FROM threat_detections", conn)
        except Exception:
            threats_df = pd.DataFrame()
        conn.close()

        # Ensure timestamp exists
        if "timestamp" in events_df.columns:
            events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], errors="coerce")
            events_df = events_df.dropna(subset=["timestamp"])
            events_df["DATE"] = events_df["timestamp"].dt.date
        else:
            st.error("SQLite events table has no 'timestamp' column.")
            return pd.DataFrame()

        # If threats table exists, merge extra Gemini data
        if not threats_df.empty:
            merged = events_df.merge(
                threats_df,
                how="left",
                left_on="id",
                right_on="event_id",
                suffixes=("", "_threat"),
            )
            return merged

        return events_df

    except Exception as e:
        st.error(f"Error reading threat_events.db: {e}")
        return pd.DataFrame()


# =====================================================
# UNIFIED LOADER (BACKEND → SQLITE)
# =====================================================
def load_data():
    df = load_from_backend()
    if df.empty:
        df = load_from_sqlite()
    return df


df = load_data()

if df.empty:
    st.error("No data available from backend or database.")
    st.stop()

# Ensure required columns
if "timestamp" not in df.columns:
    st.error("No 'timestamp' column found in loaded data.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"])
df["DATE"] = df["timestamp"].dt.date

# =====================================================
# SIDEBAR FILTERS
# =====================================================
with st.sidebar:
    st.title("CyberCyte Dashboard")
    st.header("Filters")

    min_date = df["DATE"].min()
    max_date = df["DATE"].max()

    # Default start date (up to last 30 days, but not before min_date)
    if min_date == max_date:
        start_default = min_date
    else:
        start_default = max(max_date - timedelta(days=30), min_date)

    start_date = st.date_input("Start Date", start_default, min_value=min_date, max_value=max_date)
    end_date = st.date_input("End Date", max_date, min_value=min_date, max_value=max_date)

# Filter by date
filtered_df = df[(df["DATE"] >= start_date) & (df["DATE"] <= end_date)]

# =====================================================
# EVENTS OVER TIME
# =====================================================
st.subheader("📊 Events Over Time")

events_over_time = (
    filtered_df.groupby(filtered_df["timestamp"].dt.date)
    .size()
    .reset_index(name="event_count")
    .rename(columns={filtered_df["timestamp"].dt.date.name: "date"})
)

# Ensure unique columns (no 'count' duplication)
events_over_time = events_over_time.loc[:, ~events_over_time.columns.duplicated()]

if not events_over_time.empty:
    events_over_time["date"] = pd.to_datetime(events_over_time["date"])
    line_chart = alt.Chart(events_over_time).mark_area(color="#29b5e8").encode(
        x=alt.X("date:T", title="Date", axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("event_count:Q", title="Number of Events"),
    )
    st.altair_chart(line_chart, width="stretch")
else:
    st.info("No events available in the selected date range.")

# =====================================================
# EVENT TYPE BREAKDOWN
# =====================================================
st.subheader("📁 Event Type Breakdown")

if "event_type" in filtered_df.columns:
    type_breakdown = (
        filtered_df["event_type"]
        .value_counts()
        .reset_index()
        .rename(columns={"index": "event_type", "event_type": "event_count"})
    )
    type_breakdown = type_breakdown.loc[:, ~type_breakdown.columns.duplicated()]

    if not type_breakdown.empty:
        bar_chart = alt.Chart(type_breakdown).mark_bar().encode(
            x=alt.X("event_type:N", title="Event Type"),
            y=alt.Y("event_count:Q", title="Count"),
            color="event_type:N",
        )
        st.altair_chart(bar_chart, width="stretch")
    else:
        st.info("No event type data for this date range.")
else:
    st.info("No 'event_type' column found in data.")

# =====================================================
# GEMINI CONFIDENCE OVER TIME
# =====================================================
if "gemini_confidence" in filtered_df.columns:
    st.subheader("🤖 Gemini Confidence Over Time")

    conf_df = filtered_df[["timestamp", "gemini_confidence"]].dropna()
    if not conf_df.empty:
        conf_chart = alt.Chart(conf_df).mark_line(color="#FF5C5C").encode(
            x=alt.X("timestamp:T", title="Time"),
            y=alt.Y("gemini_confidence:Q", title="Confidence"),
        )
        st.altair_chart(conf_chart, width="stretch")
    else:
        st.info("No Gemini confidence data in this time range.")

# =====================================================
# RECENT INCIDENTS TABLE
# =====================================================
st.subheader("📄 Recent Incidents")

columns_to_show = [
    col for col in [
        "timestamp",
        "source",
        "event_type",
        "anomaly_score",
        "gemini_confidence",
        "mitigation_suggestion",
        "raw_data",
    ]
    if col in filtered_df.columns
]

st.dataframe(
    filtered_df.sort_values("timestamp", ascending=False)[columns_to_show].head(25),
    width="stretch",
)

# import streamlit as st
# import pandas as pd
# import sqlite3
# import altair as alt
# from datetime import datetime, timedelta

# st.set_page_config(page_title="CyberCyte Dashboard", layout="wide")

# # =====================================================
# # LOAD TABLE FROM SQLITE
# # =====================================================
# @st.cache_data
# def load_table(table):
#     conn = sqlite3.connect("threat_events.db")
#     try:
#         df = pd.read_sql(f"SELECT * FROM {table}", conn)
#     except:
#         df = pd.DataFrame()
#     conn.close()

#     # Convert timestamp-like fields
#     for col in df.columns:
#         if any(key in col.lower() for key in ["time", "date"]):
#             df[col] = pd.to_datetime(df[col], errors="coerce")

#     return df


# # =====================================================
# # LOAD EVENTS + THREAT DATA
# # =====================================================
# events_df = load_table("events")                  # has: id, timestamp, event_type, ...
# threat_df = load_table("threat_detections")       # has: id, event_id, gemini_review, ...

# # -----------------------------------------------------
# # 1. Ensure threat table references an event correctly
# # -----------------------------------------------------
# if not threat_df.empty:
#     # Join threat → event based on event_id
#     threat_df = threat_df.merge(
#         events_df[["id", "event_type", "timestamp"]],
#         left_on="event_id",
#         right_on="id",
#         how="left",
#         suffixes=("", "_event")
#     )

#     # Always treat threats as a special event_type
#     threat_df["event_type"] = threat_df["event_type"].fillna("THREAT")


# # -----------------------------------------------------
# # 2. Combine tables
# # -----------------------------------------------------
# df = pd.concat([events_df, threat_df], ignore_index=True, sort=False)

# # -----------------------------------------------------
# # 3. Fix timestamp
# # -----------------------------------------------------
# if "timestamp" not in df.columns:
#     st.error("No usable timestamp column found.")
#     st.stop()

# df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
# df = df.dropna(subset=["timestamp"])
# df["DATE"] = df["timestamp"].dt.date


# # =====================================================
# # SIDEBAR FILTERS
# # =====================================================
# with st.sidebar:
#     st.title("CyberCyte Dashboard")

#     min_date = df["DATE"].min()
#     max_date = df["DATE"].max()

#     start_default = max(max_date - timedelta(days=30), min_date)

#     start_date = st.date_input("Start Date", start_default, min_value=min_date, max_value=max_date)
#     end_date = st.date_input("End Date", max_date, min_value=min_date, max_value=max_date)

# filtered_df = df[(df["DATE"] >= start_date) & (df["DATE"] <= end_date)]


# # =====================================================
# # EVENTS OVER TIME
# # =====================================================
# st.subheader("📊 Events Over Time")

# events_over_time = (
#     filtered_df
#     .groupby(filtered_df["timestamp"].dt.date)
#     .size()
#     .reset_index(name="event_count")    # UNIQUE NAME
# )

# events_over_time = events_over_time.loc[:, ~events_over_time.columns.duplicated()]

# line_chart = alt.Chart(events_over_time).mark_area(color="#29b5e8").encode(
#     x=alt.X("timestamp:T", title="Date"),
#     y=alt.Y("event_count:Q", title="Events"),
# )

# st.altair_chart(line_chart, use_container_width=True)


# # =====================================================
# # EVENT TYPE BREAKDOWN
# # =====================================================
# st.subheader("📁 Event Type Breakdown")

# if "event_type" in filtered_df.columns:
#     type_breakdown = (
#         filtered_df["event_type"]
#         .value_counts()
#         .reset_index()
#         .rename(columns={"index": "event_type", "event_type": "type_count"})  # UNIQUE NAME
#     )

#     type_breakdown = type_breakdown.loc[:, ~type_breakdown.columns.duplicated()]

#     bar_chart = alt.Chart(type_breakdown).mark_bar().encode(
#         x="event_type:N",
#         y="type_count:Q",
#         color="event_type:N"
#     )

#     st.altair_chart(bar_chart, use_container_width=True)
# else:
#     st.info("No event_type column found.")


# # =====================================================
# # GEMINI CONFIDENCE VISUALIZATION
# # =====================================================
# if "gemini_confidence" in filtered_df.columns:
#     st.subheader("🤖 Gemini Confidence Scores")

#     conf_df = filtered_df.dropna(subset=["gemini_confidence"])

#     conf_chart = alt.Chart(conf_df).mark_line(color="#FF5C5C").encode(
#         x="timestamp:T",
#         y="gemini_confidence:Q"
#     )

#     st.altair_chart(conf_chart, use_container_width=True)


# # =====================================================
# # RECENT INCIDENTS
# # =====================================================
# st.subheader("📄 Recent Incidents")

# st.dataframe(
#     filtered_df.sort_values("timestamp", ascending=False).head(25),
#     use_container_width=True
# )

# import requests

# EVENTS_API = "http://127.0.0.1:8000/events"
# MITS_API = "http://127.0.0.1:8000/mitigations"

# events = requests.get(EVENTS_API).json()
# mitigations = requests.get(MITS_API).json()

