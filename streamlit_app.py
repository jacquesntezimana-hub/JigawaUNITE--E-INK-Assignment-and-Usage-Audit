import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# --- DASHBOARD PRO AESTHETICS (Dark Mode & Compact Text) ---
st.markdown("""
    <style>
    /* Dark Theme Base */
    .stApp { background-color: #020617; color: #F8FAFC; }
    
    /* Top-Right Navigation */
    .stSegmentedControl { display: flex; justify-content: flex-end; margin-top: -65px; }
    
    /* Boxed Metric Cards */
    div[data-testid="stMetric"] {
        background-color: #0F172A;
        border: 1px solid #1E293B;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
    }
    [data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 700 !important; color: #38BDF8; }
    [data-testid="stMetricLabel"] { font-size: 10px !important; color: #94A3B8; font-weight: 600; text-transform: uppercase; }

    /* Compact Table Text Size */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"], .stTable {
        font-size: 11px !important;
    }

    /* Titles and Dividers */
    h1 { color: #F8FAFC; font-size: 20px !important; letter-spacing: 1px; }
    h3 { font-size: 0.85rem !important; color: #38BDF8; margin-bottom: 8px; font-weight: 600; }
    hr { border-top: 1px solid #1E293B; margin: 1rem 0; }
    
    /* Segmented Control Styling */
    div[data-testid="stSegmentedControl"] button {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        font-size: 11px !important;
        min-width: 110px;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def generate_audit_data():
    try:
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
        
        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": snipe_counts['AssignedCount'].sum(),
            "No Tablet": df[df['AssignedCount'] == 0].copy(),
            "More Than Allowed": df[df['AssignedCount'] > 1].copy(),
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        for key in summary_vals:
            if isinstance(summary_vals[key], pd.DataFrame):
                summary_vals[key]["Admin Comments / Resolution"] = ""
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- HEADER ---
h1, h2 = st.columns([1.5, 1])
with h1:
    st.title("NEWGLOBE · JIGAWAUNITE")
with h2:
    view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

st.write("---")

data, summary = generate_audit_data()

if data is not None:
    if view == "📊 SUMMARY":
        t1, t2 = st.columns(2)
        t1.metric("TOTAL ACTIVE STAFF", summary["Total Staff"])
        t2.metric("TOTAL TABLETS ASSIGNED", summary["Total Assigned"])
        
        st.write("### COMPLIANCE SUMMARY BOXES")
        m = st.columns(5)
        m[0].metric("NO TABLET", len(summary["No Tablet"]))
        m[1].metric("EXCESSIVE", len(summary["More Than Allowed"]))
        m[2].metric("IDLE USERS", len(summary["Not Using"]))
        m[3].metric("MISMATCH", len(summary["Assigned Others"]))
        m[4].metric("MULTI-LOGIN", len(summary["Multiple Devices"]))

    elif view == "📋 BREAKDOWN":
        # EXPLICIT COLUMN LIST
        breakdown_cols = [
            'EmployeeID', 'Employee Name', 'Current Academy Code', 'County', 
            'Job Title', 'Phone Number', 'Tablet ID Assigned', 
            'AssignedCount', 'Tablet ID Used', 'UsedCount', 'Matches SnipeIT?'
        ]
        st.dataframe(data[breakdown_cols], use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        base = ['EmployeeID', 'Employee Name', 'Job Title']
        comment = ['Admin Comments / Resolution']

        c1, c2 = st.columns(2)
        with c1:
            st.write("### 1. STAFF WITHOUT ASSIGNED TABLET")
            st.data_editor(summary["No Tablet"][base + comment], use_container_width=True, hide_index=True, key="e1")
        with c2:
            st.write("### 2. STAFF ASSIGNED MORE TABLETS THAN ALLOWED")
            st.data_editor(summary["More Than Allowed"][base + ['Tablet ID Assigned', 'AssignedCount'] + comment], use_container_width=True, hide_index=True, key="e2")
        
        st.write("---")
        
        c3, c4 = st.columns(2)
        with c3:
            st.write("### 3. ASSIGNED TABLET BUT NOT USING")
            st.data_editor(summary["Not Using"][base + ['Tablet ID Assigned', 'Tablet ID Used'] + comment], use_container_width=True, hide_index=True, key="e3")
        with c4:
            st.write("### 4. USING TABLETS ASSIGNED TO OTHERS")
            st.data_editor(summary["Assigned Others"][base + ['Tablet ID Assigned', 'Tablet ID Used'] + comment], use_container_width=True, hide_index=True, key="e4")
        
        st.write("---")
        
        st.write("### 5. STAFF LOGGING INTO MULTIPLE DEVICES")
        st.data_editor(summary["Multiple Devices"][base + ['Tablet ID Assigned', 'Tablet ID Used', 'UsedCount'] + comment], use_container_width=True, hide_index=True, key="e5")
