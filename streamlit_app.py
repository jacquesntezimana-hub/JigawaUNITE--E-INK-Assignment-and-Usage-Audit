import streamlit as st
import pandas as pd

st.set_page_config(page_title="Jigawa Audit Dashboard", layout="wide")

@st.cache_data
def generate_jigawa_audit():
    try:
        # 1. Load the 3 source files
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        # Clean column names
        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        # 2. Standardize Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # 3. Find Serial column in Snipe IT
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        # 4. AGGREGATE DATA
        # Snipe IT Aggregation
        snipe_grouped = snipe.groupby('JOIN_ID').agg({
            snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        # Geolocation Aggregation
        geo_grouped = geo.groupby('JOIN_ID').agg({
            'Device Serial': lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        # 5. MERGE ALL
        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        # Fill counts for logic
        df['Number of EINK Tablet Assigned'] = df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        df['Count Unique Devices Logged In'] = df['Count Unique Devices Logged In'].fillna(0).astype(int)
        
        # 6. LOGIC: Matches SnipeIT?
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set(assigned.split(',')), set(used.split(','))
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 7. CALCULATE SUMMARY METRICS
        metrics = {
            "No Tablet": len(df[df['Number of EINK Tablet Assigned'] == 0]),
            "Over Assigned": len(df[df['Number of EINK Tablet Assigned'] > 1]), # Assuming >1 is "more than allowed"
            "Not Using": len(df[(df['Number of EINK Tablet Assigned'] > 0) & (df['Count Unique Devices Logged In'] == 0)]),
            "Using Others": len(df[df['Matches SnipeIT?'] == "No"]),
            "Multiple Devices": len(df[df['Count Unique Devices Logged In'] > 1])
        }

        return df, metrics

    except Exception as e:
        st.error(f"Error: {e}")
        return None, None

# --- UI DISPLAY ---
st.title("NewGlobe · JigawaUNITE")
st.subheader("Audit Compliance Summary")

final_df, summary = generate_jigawa_audit()

if final_df is not None:
    # Top Row Metrics (Like your sample image)
    m1, m2, m3, m4, m5 = st.columns(5)
    
    m1.metric("Staff Without Tablet", summary["No Tablet"])
    m2.metric("Over-Assigned (>1)", summary["Over Assigned"])
    m3.metric("Assigned but Not Using", summary["Not Using"])
    m4.metric("Using Others' Tablet", summary["Using Others"])
    m5.metric("Multiple Devices Used", summary["Multiple Devices"])

    st.divider()

    # Detailed Table
    st.subheader("📋 Integrated Staff Audit List")
    output_cols = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'Job Title', 
                   'Tablet ID Assigned', 'Number of EINK Tablet Assigned', 
                   'Tablet ID Used', 'Count Unique Devices Logged In', 'Matches SnipeIT?']
    st.dataframe(final_df[output_cols], use_container_width=True)
    
    # Download
    csv = final_df[output_cols].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Audit Data", csv, "Jigawa_Compliance_Audit.csv", "text/csv")
