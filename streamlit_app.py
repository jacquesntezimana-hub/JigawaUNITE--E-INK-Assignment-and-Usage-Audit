import streamlit as st
import pandas as pd

# 1. Page Setup
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")
st.title("📊 JigawaUNITE: Audit Dashboard")

# 2. Loading All Datasets
@st.cache_data
def load_all_data():
    try:
        # These names must match your GitHub files exactly
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")
        status = pd.read_excel("Staff Status.xlsx")
        return active, snipe, geo, status
    except Exception as e:
        st.error(f"Missing a file or name mismatch: {e}")
        return None, None, None, None

active_df, snipe_df, geo_df, status_df = load_all_data()

# 3. Audit Logic
if active_df is not None:
    # A. Finding Staff without tablets
    # We compare Staff ID from 'Active Staff' against User ID in 'Snipe_IT'
    missing = active_df[~active_df['Staff ID'].isin(snipe_df['User ID'])]
    
    # B. Filter out Permanent Substitute Teachers (per your request)
    if 'Job Role' in missing.columns:
        filtered_missing = missing[missing['Job Role'] != 'Permanent Substitute Teacher']
    else:
        filtered_missing = missing

    # 4. Dashboard Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Active Staff", len(active_df))
    col2.metric("Missing Tablets", len(filtered_missing))
    col3.metric("Snipe Records", len(snipe_df))

    st.divider()

    # 5. Show the List
    st.subheader("🚨 Staff Missing Tablet Assignments")
    st.dataframe(filtered_missing, use_container_width=True)
    
    # 6. Geolocation Sync Check
    st.subheader("📍 Recent Geolocation Activity")
    st.dataframe(geo_df.head(10), use_container_width=True)

else:
    st.info("Check your GitHub filenames. They must be: 'Active Staff.xlsx', 'Snipe_IT.xlsx', 'Geolocation Sync 07_10 Apr.xlsx', and 'Staff Status.xlsx'")
