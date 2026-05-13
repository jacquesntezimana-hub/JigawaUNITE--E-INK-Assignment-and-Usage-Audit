import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 30px; font-weight: bold; color: #1E3A8A; }
    .stSegmentedControl { display: flex; justify-content: flex-end; }
    div[data-testid="stSegmentedControl"] button { min-width: 130px; border-radius: 20px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def generate_audit_data():
    try:
        # Load Files
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        # Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        # Aggregations
        snipe_grouped = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_grouped = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        # Final Merge
        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # Match Logic
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set([s.strip() for s in assigned.split(',')]), set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # Prepare Metrics Dataframes
        is_ht = df['Job Title'].str.contains('headteacher|head teacher', case=False, na=False)
        
        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": snipe_counts['AssignedCount'].sum(),
            "No Tablet": df[df['AssignedCount'] == 0].copy(),
            "More Than Allowed": df[(df['AssignedCount'] > 1) & ~((is_ht) & (df['AssignedCount'] == 2))].copy(),
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        
        # Add the Comment Column to each escalation dataframe
        for key in ["No Tablet", "More Than Allowed", "Not Using", "Assigned Others", "Multiple Devices"]:
            summary_vals[key]["Admin Comments / Resolution"] = ""

        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- HEADER ---
h1, h2 = st.columns([1.5, 1])
with h1:
    st.title("NewGlobe · JigawaUNITE")
with h2:
    view = st.segmented_control("Navigation", options=["📊 Summary", "📋 Breakdown", "🚨 Escalation"], selection_mode="single", default="📊 Summary", label_visibility="collapsed")

st.write("---")

data, summary = generate_audit_data()

if data is not None:
    total_pop = summary["Total Staff"]

    if view == "📊 Summary":
        t1, t2 = st.columns(2)
        t1.metric("Total Active Staff", summary["Total Staff"])
        t2.metric("Total Number of Assigned Tablets", summary["Total Assigned"])
        st.write("### Compliance Metrics")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Staff without assigned tablet", len(summary["No Tablet"]), f"{(len(summary['No Tablet'])/total_pop)*100:.1f}%")
        m2.metric("Staff assigned more tablets than allowed", len(summary["More Than Allowed"]), f"{(len(summary['More Than Allowed'])/total_pop)*100:.1f}%")
        m3.metric("Staff assigned tablet but not using/log in it", len(summary["Not Using"]), f"{(len(summary['Not Using'])/total_pop)*100:.1f}%")
        m4.metric("Staff using tablets assigned to others", len(summary["Assigned Others"]), f"{(len(summary['Assigned Others'])/total_pop)*100:.1f}%")
        m5.metric("Staff logging into multiple devices", len(summary["Multiple Devices"]), f"{(len(summary['Multiple Devices'])/total_pop)*100:.1f}%")

    elif view == "📋 Breakdown":
        st.subheader("Full Staff Audit List")
        st.dataframe(data, use_container_width=True, hide_index=True)

    elif view == "🚨 Escalation":
        st.header("🚨 Priority Escalation Action Lists")
        st.info("💡 You can type directly into the 'Admin Comments' column to record notes.")
        
        common = ['EmployeeID', 'Employee Name', 'Job Title', 'Admin Comments / Resolution']

        with st.expander("1. Staff without assigned tablet", expanded=True):
            st.data_editor(summary["No Tablet"][common], use_container_width=True, hide_index=True, key="ed1")

        with st.expander("2. Staff assigned more tablets than allowed", expanded=True):
            st.data_editor(summary["More Than Allowed"][common + ['AssignedCount']], use_container_width=True, hide_index=True, key="ed2")

        with st.expander("3. Staff assigned tablet but not using/log in it", expanded=True):
            st.data_editor(summary["Not Using"][common + ['Tablet ID Assigned']], use_container_width=True, hide_index=True, key="ed3")

        with st.expander("4. Staff using tablets assigned to others", expanded=True):
            st.data_editor(summary["Assigned Others"][common + ['Tablet ID Assigned', 'Tablet ID Used']], use_container_width=True, hide_index=True, key="ed4")

        with st.expander("5. Staff logging into multiple devices", expanded=True):
            st.data_editor(summary["Multiple Devices"][common + ['UsedCount']], use_container_width=True, hide_index=True, key="ed5")
