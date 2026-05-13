import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# 2. Advanced Custom CSS for the "Professional Look"
st.markdown("""
    <style>
    /* Dark Theme background for the whole app */
    .main { background-color: #0e1117; }
    
    /* Top-right Navigation Styling */
    .stSegmentedControl { display: flex; justify-content: flex-end; padding-top: 10px; }
    div[data-testid="stSegmentedControl"] button { 
        background-color: #1f2937; color: white; border-radius: 8px; border: 1px solid #374151;
    }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background-color: #3b82f6 !important; border-color: #3b82f6;
    }

    /* Metric Card Styling */
    [data-testid="stMetricValue"] { font-size: 36px; font-weight: 800; color: #fbbf24; }
    [data-testid="stMetricLabel"] { font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; }
    
    /* Data Editor / Table Styling */
    .stDataFrame { border: 1px solid #374151; border-radius: 12px; }
    
    /* Section Headers */
    h1, h2, h3 { color: #f3f4f6; font-family: 'Inter', sans-serif; }
    hr { border-top: 1px solid #374151; }
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
        
        # Matches logic
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set([s.strip() for s in assigned.split(',')]), set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")
        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # Filters with Headteacher Exception
        is_ht = df['Job Title'].str.contains('headteacher|head teacher', case=False, na=False)
        
        summary_vals = {
            "Total Staff": len(active),
            "No Tablet": df[df['AssignedCount'] == 0].copy(),
            "More Than Allowed": df[(df['AssignedCount'] > 1) & ~((is_ht) & (df['AssignedCount'] == 2))].copy(),
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        for key in summary_vals:
            if isinstance(summary_vals[key], pd.DataFrame):
                summary_vals[key]["Admin Comments / Resolution"] = ""
        return df, summary_vals
    except Exception as e:
        st.error(f"Setup Error: {e}")
        return None, None

# --- TOP ROW (Title and Right Navigation) ---
h_left, h_right = st.columns([1.5, 1])
with h_left:
    st.title("NewGlobe · JigawaUNITE")
    st.caption("Operational Health & Geolocation Compliance Audit")
with h_right:
    view = st.segmented_control(
        "Menu", options=["Summary", "Breakdown", "Escalation"], 
        selection_mode="single", default="Summary", label_visibility="collapsed"
    )

st.write("---")

data, summary = generate_audit_data()

if data is not None:
    if view == "Summary":
        # Metric Grid
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("No Assigned Tablet", len(summary["No Tablet"]))
        m2.metric("Excess Devices", len(summary["More Than Allowed"]))
        m3.metric("Assigned but Idle", len(summary["Not Using"]))
        m4.metric("Non-Compliant ID", len(summary["Assigned Others"]))
        m5.metric("Multiple Logins", len(summary["Multiple Devices"]))

    elif view == "Breakdown":
        st.dataframe(data, use_container_width=True, hide_index=True)

    elif view == "Escalation":
        st.subheader("🚨 Priority Action Items")
        cols = ['EmployeeID', 'Employee Name', 'Admin Comments / Resolution']
        
        # Side-by-Side Rows
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.write("### 1. Missing Tablets")
            st.data_editor(summary["No Tablet"][cols], use_container_width=True, hide_index=True, key="q1")
        with r1_c2:
            st.write("### 2. Excess Devices")
            st.data_editor(summary["More Than Allowed"][cols], use_container_width=True, hide_index=True, key="q2")

        st.write("---")
        
        r2_c1, r2_c2 = st.columns(2)
        with r2_c1:
            st.write("### 3. Idle Users")
            st.data_editor(summary["Not Using"][cols], use_container_width=True, hide_index=True, key="q3")
        with r2_c2:
            st.write("### 4. ID Mismatches")
            st.data_editor(summary["Assigned Others"][cols], use_container_width=True, hide_index=True, key="q4")
