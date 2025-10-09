import streamlit as st
import requests
import pandas as pd

API_URL = "https://localhost:8443/telemetry"

st.title("Gemini Threat Dashboard")

if st.button("Load Latest Telemetry"):
    resp = requests.get(API_URL, verify="certificates/ca-cert.pem")
    df = pd.DataFrame(resp.json())
    st.dataframe(df)
    st.line_chart(df["size"])
