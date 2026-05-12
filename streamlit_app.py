import streamlit as st
import pandas as pd

# Set page to wide mode
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# Custom CSS for the NewGlobe "Dark Mode" feel
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 32px; font-weight: bold; }
    [data-testid="stMetricDelta"] { font-size: 16px; }
    .main { background-color: #0e1117; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def generate_jigawa_audit():
    try:
        # 1. Load Files
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        # 2. Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        # 3. Aggregations
        snipe_grouped = snipe.groupby('JOIN_ID').agg({
            snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_grouped = geo.groupby('JOIN_ID').agg({
            'Device Serial': lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        # 4. Final Merge
        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        df['Number of EINK Tablet Assigned'] = df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        df['Count Unique Devices Logged In'] = df['Count Unique Devices Logged In'].fillna(0).astype(int)
        
        # 5. Logic Check
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set(assigned.split(',')), set(used.split(','))
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 6. Metric Calculations
        total_staff = len(active)
        summary_vals = {
            "Total Staff": total_staff,
            "Total Assigned": snipe_counts['Number of EINK Tablet Assigned'].sum(),
            "Staff without assigned tablet": len(df[df['Number of EINK Tablet Assigned'] == 0]),
            "Staff assigned more tablets than allowed": len(df[df['Number of EINK Tablet Assigned'] > 1]),
            "Staff assigned tablet but not using/log in it": len(df[(df['Number of EINK Tablet Assigned'] > 0) & (df['Count Unique Devices Logged In'] == 0)]),
            "Staff using tablets assigned to others": len(df[df['Matches SnipeIT?'] == "No"]),
            "Staff logging into multiple devices": len(df[df['Count Unique Devices Logged In'] > 1])
        }

        return df, summary_vals

    except Exception as e:
        st.error(f"Error: {e}")
        return None, None

# --- HEADER SECTION ---
st.title("NewGlobe · JigawaUNITE")
st.markdown("#### Tablet Compliance Audit")

final_df, summary = generate_jigawa_audit()

if final_df is not None:
    # --- NAVIGATION TABS ---
    # This creates the menu you highlighted in your image
    tab_summary, tab_breakdown = st.tabs(["📊 Summary", "📋 Breakdown"])

    # --- SUMMARY TAB ---
    with tab_summary:
        total_pop = summary["Total Staff"]
        
        # Totals Row
        t1, t2 = st.columns(2)
        t1.metric("Total Active Staff", summary["Total Staff"])
        t2.metric("Total Number of Assigned Tablets", summary["Total Assigned"])
        
        st.write("---")
        
        # Compliance Boxes Row
        m1, m2, m3, m4, m5 = st.columns(5)
        
        m1.metric("Staff without assigned tablet", summary["Staff without assigned tablet"], 
                  f"{(summary['Staff without assigned tablet']/total_pop)*100:.1f}%")
        
        m2.metric("Staff assigned more tablets than allowed", summary["Staff assigned more tablets than allowed"], 
                  f"{(summary['Staff assigned more tablets than allowed']/total_pop)*100:.1f}%")
        
        m3.metric("Staff assigned tablet but not using/log in it", summary["Staff assigned tablet but not using/log in it"], 
                  f"{(summary['Staff assigned tablet but not using/log in it']/total_pop)*100:.1f}%")
        
        m4.metric("Staff using tablets assigned to others", summary["Staff using tablets assigned to others"], 
                  f"{(summary['Staff using tablets assigned to others']/total_pop)*100:.1f}%")
        
        m5.metric("Staff logging into multiple devices", summary["Staff logging into multiple devices"], 
                  f"{(summary['Staff logging into multiple devices']/total_pop)*100:.1f}%")

    # --- BREAKDOWN TAB ---
    with tab_breakdown:
        st.subheader("Detailed Compliance Breakdown")
        
        output_cols = [
            'EmployeeID', 'Employee Name', 'Current Academy Code', 'Job Title', 
            'Tablet ID Assigned', 'Number of EINK Tablet Assigned', 
            'Tablet ID Used', 'Count Unique Devices Logged In', 'Matches SnipeIT?'
        ]
        
        st.dataframe(final_df[output_cols], use_container_width=True, hide_index=True)
        
        # Export Button only in Breakdown
        csv = final_df[output_cols].to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export CSV", csv, "Jigawa_Audit_Breakdown.csv", "text/csv")
