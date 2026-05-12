import streamlit as st
import pandas as pd

st.title("📊 JigawaUNITE Audit")

try:
    active = pd.read_excel("Active Staff.xlsx")
    st.success("✅ Connected to Data!")
    st.metric("Total Staff", len(active))
    st.dataframe(active.head())
except Exception as e:
    st.error(f"Waiting for files... Error: {e}")
