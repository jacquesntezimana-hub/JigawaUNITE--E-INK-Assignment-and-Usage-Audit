import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# --- HIGH-END AESTHETIC CSS ---
st.markdown("""
    <style>
    /* Main background and font */
    .stApp { background-color: #F8FAFC; }
    
    /* Top-Right Navigation Alignment */
    .stSegmentedControl { display: flex; justify-content: flex-end; margin-top: -60px; }
    
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #E2E8F0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    [data-testid="stMetricValue"] { font-size: 32px !important; font-weight: 700 !important; color: #1E3A8A; }
    [data-testid="stMetricLabel"] { font-size: 14px !important; color: #64748B; font-weight: 600; }

    /* Segmented Control Buttons */
    div[data-testid="stSegmentedControl"] button {
        border-radius: 8px !important;
        min-width: 120px;
        font-weight: 600;
    }

    /* Table Headers */
    h3 { 
        font-size: 1.1rem !important; 
        color: #1E293B; 
        font-weight: 700; 
        margin-bottom: 10px;
        border-left: 4px solid #3B82F6;
        padding-left: 10px;
    }
    
    /* Clean Divider */
    hr { margin-top: 1rem; margin-bottom: 1.5rem; border: 0; border-top: 1px solid #E2E8F0; }
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

        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        snipe_grouped = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_grouped = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set([s.strip() for s in assigned.split(',')]), set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")
        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

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
        for key in ["No Tablet", "More Than Allowed", "Not Using", "Assigned Others", "Multiple Devices"]:
            summary_vals[key]["Admin Comments / Resolution"] = ""
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- HEADER ---
st.title("NewGlobe · JigawaUNITE")
view = st.segmented_control("Navigation", options=["📊 Summary", "📋 Breakdown", "🚨 Escalation"], selection_mode="single", default="📊 Summary", label_visibility="collapsed")
st.write("---")

data, summary = generate_audit_data()

if data is not None:
    total_pop = summary["Total Staff"]

    if view == "📊 Summary":
        t1, t2 = st.columns(2)
        t1.metric("Total Active Staff", summary["Total Staff"])
        t2.metric("Total Assigned Tablets", summary["Total Assigned"])
        st.write("### Compliance Metrics")
        m = st.columns(5)
        m[0].metric("No Tablet", len(summary["No Tablet"]), f"{(len(summary['No Tablet'])/total_pop)*100:.1f}%")
        m[1].metric("Excessive", len(summary["More Than Allowed"]), f"{(len(summary['More Than Allowed'])/total_pop)*100:.1f}%")
        m[2].metric("Not Using", len(summary["Not Using"]), f"{(len(summary['Not Using'])/total_pop)*100:.1f}%")
        m[3].metric("Mismatch", len(summary["Assigned Others"]), f"{(len(summary['Assigned Others'])/total_pop)*100:.1f}%")
        m[4].metric("Multi-Device", len(summary["Multiple Devices"]), f"{(len(summary['Multiple Devices'])/total_pop)*100:.1f}%")

    elif view == "📋 Breakdown":
        st.dataframe(data, use_container_width=True, hide_index=True)

    elif view == "🚨 Escalation":
        common = ['EmployeeID', 'Employee Name', 'Admin Comments / Resolution']
        
        # SIDE-BY-SIDE GRID (Lists 1 & 2)
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 1. No Assigned Tablet")
            st.data_editor(summary["No Tablet"][common], use_container_width=True, hide_index=True, key="ed1")
        with c2:
            st.write("### 2. Excess Devices")
            st.data_editor(summary["More Than Allowed"][common + ['AssignedCount']], use_container_width=True, hide_index=True, key="ed2")

        st.write("---")

        # SIDE-BY-SIDE GRID (Lists 3 & 4)
        c3, c4 = st.columns(2)
        with c3:
            st.write("### 3. Idle Users (No Log-in)")
            st.data_editor(summary["Not Using"][common], use_container_width=True, hide_index=True, key="ed3")
        with c4:
            st.write("### 4. Assigned to Others")
            st.data_editor(summary["Assigned Others"][common], use_container_width=True, hide_index=True, key="ed4")

        st.write("---")

        st.write("### 5. Logging into Multiple Devices")
        st.data_editor(summary["Multiple Devices"][common + ['UsedCount']], use_container_width=True, hide_index=True, key="ed5")
