# # dashboard.py
# import streamlit as st
# import requests
# import pandas as pd
# import time
# import datetime

# # ==============================
# # CONFIGURATION
# # ==============================
# st.set_page_config(
#     page_title="AI Threat Detection Dashboard",
#     layout="wide"
# )

# API_URL = "http://127.0.0.1:8000/get_latest_threats"  # FastAPI endpoint
# REFRESH_INTERVAL = 5  # seconds between refreshes

# # ==============================
# # PAGE HEADER
# # ==============================
# st.title("🛡 Cyber-Cyte AI Threat Response Dashboard")
# st.caption("Powered by osquery • Zeek • Isolation Forest / Amber • Gemini")

# # ==============================
# # DATA FETCH FUNCTION
# # ==============================
# def fetch_threat_data():
#     """Pull latest AI-reviewed threat data from FastAPI backend."""
#     try:
#         response = requests.get(API_URL)
#         response.raise_for_status()
#         return pd.DataFrame(response.json())
#     except requests.exceptions.RequestException as e:
#         st.error(f"⚠️ Cannot connect to backend: {e}")
#         return pd.DataFrame()

# # ==============================
# # AUTO-REFRESH LOOP
# # ==============================
# while True:
#     # Clear and re-render dashboard each loop
#     st.empty()

#     # Fetch data
#     data = fetch_threat_data()
#     # Convert ISO timestamp to simpler readable format
#     if 'timestamp' in data.columns:
#         data['timestamp'] = pd.to_datetime(data['timestamp'], errors='coerce').dt.strftime("%b %d, %Y %I:%M %p")


#     if data.empty:
#         st.info("No AI-reviewed threats yet. Waiting for anomaly events...")
#     else:
#         # --- KPI / METRICS SECTION ---
#         st.subheader("📊 System Overview")
#         col1, col2, col3 = st.columns(3)
#         col1.metric("Total Reviewed Events", len(data))
#         col2.metric("Max Gemini Confidence", f"{data['gemini_confidence'].max() * 100:.2f}%")
#         col3.metric("Recent Threat Source", data['source'].iloc[0])

#         st.markdown("---")

#         # --- DATA TABLE SECTION ---
#         st.subheader("🧠 AI-Reviewed Threat Logs")

#         df_display = data[[
#             'timestamp', 'source', 'event_type',
#             'anomaly_score', 'gemini_confidence',
#             'mitigation_suggestion', 'raw_data'
#         ]].rename(columns={
#             'timestamp': 'Timestamp',
#             'source': 'Source',
#             'event_type': 'Event Type',
#             'anomaly_score': 'ML Score',
#             'gemini_confidence': 'Gemini Confidence',
#             'mitigation_suggestion': 'Mitigation Suggestion',
#             'raw_data': 'Raw Event Log'
#         })

#         # Apply color styling
#         def color_confidence(val):
#             if isinstance(val, (int, float)):
#                 if val > 0.8:
#                     return 'background-color: #ff4c4c; color: white'  # High
#                 elif val > 0.5:
#                     return 'background-color: orange'  # Medium
#                 elif val > 0.2:
#                     return 'background-color: yellow'  # Low
#             return ''

#         st.dataframe(
#             df_display.style.applymap(color_confidence, subset=['Gemini Confidence']),
#             use_container_width=True,
#             height=500
#         )

#     # --- FOOTER ---
#     st.markdown("---")
#     st.caption(f"🔁 Auto-refresh every {REFRESH_INTERVAL} seconds • Data source: FastAPI @ {API_URL}")
#     st.caption(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

#     # Wait before refresh
#     time.sleep(REFRESH_INTERVAL)

#     # Rerun the script
#     st.rerun()

##-------------NEW DASH------------------
# import streamlit as st
# import pandas as pd
# import requests
# import time
# import datetime

# # -------------------------------
# # PAGE CONFIG
# # -------------------------------
# st.set_page_config(page_title="Cyber-Cyte Dashboard", layout="wide")
# st.title("🔒 Cyber-Cyte Dashboard")
# st.caption("Autonomous AI Cyber Defense • Real-Time Threat Monitoring")

# # -------------------------------
# # AUTO REFRESH CONTROL
# # -------------------------------
# st.sidebar.markdown("### 🔄 Auto Refresh")
# refresh_rate = st.sidebar.slider("Refresh every (seconds):", 5, 60, 10)
# st.sidebar.write("⏱️ Refresh interval:", refresh_rate, "seconds")

# # -------------------------------
# # TABS (MATCHING GCP VM)
# # -------------------------------
# tabs = st.tabs(["Home", "Clients", "Networks", "Threats", "Add Entry", "AI Threat Detection"])

# # ============================================================
# # HOME TAB
# # ============================================================
# with tabs[0]:
#     st.header("📊 System Summary")
#     col1, col2, col3 = st.columns(3)
#     col1.metric("Total Clients", "0")
#     col2.metric("Monitored Networks", "0")
#     col3.metric("Detected Threats", "0")
#     st.caption("System overview (demo mode).")

# # ============================================================
# # CLIENTS TAB
# # ============================================================
# with tabs[1]:
#     st.header("👥 Clients")
#     st.info("Client list goes here (Firebase disabled for demo).")

# # ============================================================
# # NETWORKS TAB
# # ============================================================
# with tabs[2]:
#     st.header("🌐 Networks")
#     st.info("Network detections go here (Firebase disabled for demo).")

# # ============================================================
# # THREATS TAB (PCAPs)
# # ============================================================
# with tabs[3]:
#     st.header("🚨 PCAP Threat Events")
#     st.info("PCAP events from Firebase go here (disabled for demo).")

# # ============================================================
# # ADD ENTRY TAB
# # ============================================================
# with tabs[4]:
#     st.header("📝 Add PCAP Entry")
#     st.info("Add new PCAP entries to Firestore (disabled for demo).")

# # ============================================================
# # AI THREAT DETECTION TAB (BACKEND → DASHBOARD)
# # ============================================================
# with tabs[5]:
#     st.header("🛡 AI Threat Detection (FastAPI Backend)")

#     API_URL = "http://127.0.0.1:8000/get_latest_threats"

#     # fetch from backend
#     def fetch_ai_threats():
#         try:
#             response = requests.get(API_URL)
#             return pd.DataFrame(response.json())
#         except:
#             return pd.DataFrame()

#     data = fetch_ai_threats()

#     if data.empty:
#         st.warning("Waiting for AI-reviewed threats...")
#     else:
#         # ============================
#         # METRICS
#         # ============================
#         st.subheader("📈 AI Detection Summary")
#         col1, col2, col3 = st.columns(3)
#         col1.metric("Total Reviewed Events", len(data))
#         col2.metric("Max Confidence", f"{data['gemini_confidence'].max()*100:.2f}%")
#         col3.metric("Latest Source", data['source'].iloc[0])

#         st.markdown("---")

#         # ============================
#         # CLEAN TIMESTAMP
#         # ============================
#         data['timestamp'] = pd.to_datetime(
#             data['timestamp'], errors="coerce"
#         ).dt.strftime("%b %d, %Y %I:%M %p")

#         # Rename columns for UI
#         df = data.rename(columns={
#             "timestamp": "Timestamp",
#             "source": "Source",
#             "event_type": "Event Type",
#             "anomaly_score": "ML Score",
#             "gemini_confidence": "Gemini Confidence",
#             "mitigation_suggestion": "Mitigation",
#             "raw_data": "Raw Event"
#         })

#         # Color code (like GCP VM)
#         def color_conf(val):
#             if val > 0.8: return "background-color:#ff4c4c;color:white"
#             elif val > 0.5: return "background-color:orange"
#             elif val > 0.2: return "background-color:yellow"
#             return ""

#         st.subheader("🧠 AI-Reviewed Threat Events")
#         st.dataframe(
#             df.style.applymap(color_conf, subset=["Gemini Confidence"]),
#             use_container_width=True,
#             height=500
#         )

#     st.markdown("---")
#     st.caption(
#         f"🔄 Auto-refresh: {refresh_rate}s • Last updated: "
#         f"{datetime.datetime.now().strftime('%I:%M:%S %p')}"
#     )

# # ============================================================
# # AUTO REFRESH LOOP
# # ============================================================
# time.sleep(refresh_rate)
# st.rerun()
#############NEW NEW NEW DASD DASH DASH##################
import streamlit as st
import pandas as pd
import requests
import time
import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import firestore as gcf

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(page_title="Cyber-Cyte Dashboard", layout="wide")
st.title("🔒 Cyber-Cyte Dashboard")
st.caption("Autonomous AI Cyber Defense • Firebase + FastAPI Integration")

# -------------------------------
# AUTO REFRESH SIDEBAR
# -------------------------------
st.sidebar.markdown("### 🔄 Auto Refresh")
refresh_rate = st.sidebar.slider("Refresh every (seconds):", 5, 60, 10)
st.sidebar.write("⏱ Refresh interval:", refresh_rate, "seconds")

# -------------------------------
# FIREBASE INITIALIZATION
# -------------------------------
firebase_path = "firebase_key.json"  # <-- adjust if needed

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------------------------------
# TABS (GCP VM STYLE)
# -------------------------------
tabs = st.tabs([
    "Home",
    "Clients",
    "Networks",
    "Threats",
    "Add Entry",
    "AI Threat Detection"
])

# ============================================================
# HOME TAB
# ============================================================
with tabs[0]:
    st.header("📊 System Summary")

    total_clients = len(list(db.collection("clients").stream()))
    total_networks = len(list(db.collection("networks").stream()))
    total_pcaps = len(list(db.collection("pcaps").stream()))

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Clients", total_clients)
    col2.metric("Monitored Networks", total_networks)
    col3.metric("Detected PCAP Events", total_pcaps)

    st.caption("Live Firebase-backed system summary.")

# ============================================================
# CLIENTS TAB
# ============================================================
with tabs[1]:
    st.header("👥 Registered Clients")

    client_docs = db.collection("clients").stream()
    client_data = [doc.to_dict() for doc in client_docs]

    if client_data:
        df_clients = pd.DataFrame(client_data)
        st.dataframe(df_clients, use_container_width=True)
    else:
        st.info("No client data found in Firebase.")

# ============================================================
# NETWORKS TAB
# ============================================================
with tabs[2]:
    st.header("🌐 Network Data")

    network_docs = db.collection("networks").stream()
    network_data = [doc.to_dict() for doc in network_docs]

    if network_data:
        df_networks = pd.DataFrame(network_data)
        st.dataframe(df_networks, use_container_width=True)
    else:
        st.info("No network entries found in Firebase.")

# ============================================================
# PCAP THREAT TAB
# ============================================================
with tabs[3]:
    st.header("🚨 PCAP Threat Events (Firebase)")

    pcap_docs = db.collection("pcaps").stream()
    pcap_data = [doc.to_dict() for doc in pcap_docs]

    if pcap_data:
        df_pcaps = pd.DataFrame(pcap_data)
        st.dataframe(df_pcaps, use_container_width=True)
    else:
        st.warning("No PCAP entries available in Firebase.")

    st.caption("Real-time PCAP logging from Firestore.")

# ============================================================
# ADD ENTRY TAB
# ============================================================
with tabs[4]:
    st.header("📝 Add New PCAP Entry to Firebase")

    with st.form("add_pcap_form"):
        doc_id = st.text_input("Document ID (e.g., capture1)")
        source = st.text_input("Source (e.g., Wireshark)")
        uploaded_by = st.text_input("Uploaded by")
        event_type = st.selectbox(
            "Event Type",
            ["Threat Detection", "Monitoring", "Error Log", "Mitigation"]
        )
        description = st.text_area("Description")

        submitted = st.form_submit_button("Add Entry")

    if submitted:
        if doc_id:
            doc_ref = db.collection("pcaps").document(doc_id)
            doc_ref.set({
                "source": source,
                "uploaded_by": uploaded_by,
                "event_type": event_type,
                "description": description,
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            st.success(f"🔥 Added '{doc_id}' to Firebase successfully.")
            st.rerun()
        else:
            st.error("⚠️ Please enter a Document ID.")

# ============================================================
# AI THREAT DETECTION TAB (FASTAPI BACKEND)
# ============================================================
with tabs[5]:
    st.header("🛡 AI Threat Detection (FastAPI Backend)")

    API_URL = "http://127.0.0.1:8000/get_latest_threats"

    def fetch_ai_threats():
        try:
            r = requests.get(API_URL)
            return pd.DataFrame(r.json())
        except:
            return pd.DataFrame()

    data = fetch_ai_threats()

    if data.empty:
        st.warning("Waiting for AI-reviewed threats...")
    else:
        # METRICS
        st.subheader("📈 AI Detection Summary")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Reviewed Events", len(data))
        col2.metric("Max Confidence", f"{data['gemini_confidence'].max()*100:.2f}%")
        col3.metric("Latest Source", data['source'].iloc[0])

        st.markdown("---")

        # CLEAN TIMESTAMPS
        data["timestamp"] = pd.to_datetime(
            data["timestamp"], errors="coerce"
        ).dt.strftime("%b %d, %Y %I:%M %p")

        df = data.rename(columns={
            "timestamp": "Timestamp",
            "source": "Source",
            "event_type": "Event Type",
            "anomaly_score": "ML Score",
            "gemini_confidence": "Gemini Confidence",
            "mitigation_suggestion": "Mitigation",
            "raw_data": "Raw Event Log"
        })

        # COLOR MAP
        def color_conf(val):
            if val > 0.8: return "background-color:#ff4c4c;color:white"
            elif val > 0.5: return "background-color:orange"
            elif val > 0.2: return "background-color:yellow"
            return ""

        st.subheader("🧠 AI-Reviewed Threat Events")
        st.dataframe(
            df.style.applymap(color_conf, subset=["Gemini Confidence"]),
            use_container_width=True,
            height=500
        )

    st.markdown("---")
    st.caption(
        f"🔄 Auto-refresh: {refresh_rate}s • Updated at "
        f"{datetime.datetime.now().strftime('%I:%M:%S %p')}"
    )

# ============================================================
# AUTO REFRESH LOOP
# ============================================================
time.sleep(refresh_rate)
st.rerun()
