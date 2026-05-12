import streamlit as st
import pandas as pd

st.set_page_config(page_title="Jigawa Audit Report", layout="wide")
st.title("📊 Integrated Audit: Staff & Device Report")

@st.cache_data
def generate_jigawa_audit():
    try:
        # 1. Load the 3 source files
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        # 2. Standardize Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # 3. CALCULATIONS
        # A. Count Tablets assigned per user from Snipe_IT
        tablet_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')

        # B. Count Unique Devices Logged In from Geolocation
        # (Assumes Geolocation file has a 'Device Serial' or similar column to count)
        geo_unique = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')

        # 4. PERFORM MERGES
        # Start with Active Staff to keep all Employee IDs
        df = pd.merge(active, tablet_counts, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_unique, on='JOIN_ID', how='left')
        
        # Merge Geolocation details to get the 'Device Serial' column itself
        # We use drop_duplicates to avoid multiplying rows if one user has many pings
        geo_details = geo[['JOIN_ID', 'Device Serial']].drop_duplicates('JOIN_ID')
        df = pd.merge(df, geo_details, on='JOIN_ID', how='left')

        # 5. LOGIC: Matches SnipeIT?
        # Compares 'Serial' from Active Staff vs 'Device Serial' from Geolocation
        def check_match(row):
            s_active = str(row.get('Serial', '')).strip().lower()
            s_geo = str(row.get('Device Serial', '')).strip().lower()
            if s_active == 'nan' or s_geo == 'nan' or not s_active or not s_geo:
                return "No Data"
            return "Yes" if s_active == s_geo else "No"

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 6. FINAL COLUMN SELECTION (Your specific list)
        output_columns = [
            'EmployeeID',
            'Employee Name',
            'Current Academy Code',
            'Job Title',
            'Serial',
            'Number of EINK Tablet Assigned',
            'Device Serial',
            'Count Unique Devices Logged In',
            'Matches SnipeIT?'
        ]

        # Fill numeric NaNs with 0 for the counts
        df['Number of EINK Tablet Assigned'] = df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        df['Count Unique Devices Logged In'] = df['Count Unique Devices Logged In'].fillna(0).astype(int)

        return df[output_columns]

    except Exception as e:
        st.error(f"Mapping Error: {e}")
        return None

# --- DISPLAY ---
report_df = generate_jigawa_audit()

if report_df is not None:
    st.dataframe(report_df, use_container_width=True)
    
    # Download Button
    csv = report_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Integrated Audit Report",
        data=csv,
        file_name="Jigawa_Audit_Report.csv",
        mime="text/csv"
    )
