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

        # Clean all column names of invisible spaces
        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        # 2. Standardize Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # 3. DYNAMIC SEARCH FOR 'SERIAL' in Snipe_IT
        # Looks for 'Serial', 'Serial Number', etc. in the Snipe_IT file
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        if not snipe_serial_col:
            st.error(f"Could not find a 'Serial' column in Snipe_IT. Available: {list(snipe.columns)}")
            return None

        # 4. CALCULATIONS
        # A. Count Tablets assigned per user from Snipe_IT
        tablet_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')

        # B. Count Unique Devices Logged In from Geolocation
        geo_unique = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')

        # 5. PERFORM MERGES
        # Start with Active Staff to keep all payroll records
        df = pd.merge(active, tablet_counts, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_unique, on='JOIN_ID', how='left')
        
        # Merge Snipe_IT details to get the 'Official Serial'
        # We drop duplicates to ensure one row per user
        snipe_details = snipe[['JOIN_ID', snipe_serial_col]].drop_duplicates('JOIN_ID')
        df = pd.merge(df, snipe_details, on='JOIN_ID', how='left')

        # Merge Geolocation details to get the 'Device Serial' (actual usage)
        geo_details = geo[['JOIN_ID', 'Device Serial']].drop_duplicates('JOIN_ID')
        df = pd.merge(df, geo_details, on='JOIN_ID', how='left')

        # 6. LOGIC: Matches SnipeIT?
        # Compares 'Official Serial' (Snipe_IT) vs 'Device Serial' (Geo Sync)
        def check_match(row):
            s_official = str(row.get(snipe_serial_col, '')).strip().lower()
            s_actual = str(row.get('Device Serial', '')).strip().lower()
            
            if s_official in ['nan', 'none', ''] or s_actual in ['nan', 'none', '']:
                return "No Data"
            return "Yes" if s_official == s_actual else "No"

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 7. FINAL COLUMN SELECTION
        output_mapping = {
            'EmployeeID': 'EmployeeID',
            'Employee Name': 'Employee Name',
            'Current Academy Code': 'Current Academy Code',
            'Job Title': 'Job Title',
            snipe_serial_col: 'Serial', # This is your 'Serial' from Snipe_IT
            'Number of EINK Tablet Assigned': 'Number of EINK Tablet Assigned',
            'Device Serial': 'Device Serial',
            'Count Unique Devices Logged In': 'Count Unique Devices Logged In',
            'Matches SnipeIT?': 'Matches SnipeIT?'
        }

        # Select and Rename for the final view
        final_df = df[list(output_mapping.keys())].rename(columns=output_mapping)
        
        # Format numbers
        final_df['Number of EINK Tablet Assigned'] = final_df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        final_df['Count Unique Devices Logged In'] = final_df['Count Unique Devices Logged In'].fillna(0).astype(int)

        return final_df

    except Exception as e:
        st.error(f"Mapping Error: {e}")
        return None

# --- DISPLAY ---
report_df = generate_jigawa_audit()

if report_df is not None:
    st.dataframe(report_df, use_container_width=True)
    
    csv = report_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Final Audit Report", csv, "Jigawa_Audit_Final.csv", "text/csv")
