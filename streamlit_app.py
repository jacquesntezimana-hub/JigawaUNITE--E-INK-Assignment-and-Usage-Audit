import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_config = st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME REPAIR: NO WHITE BOXES, HIGH VISIBILITY ---
st.markdown("""
    <style>
    /* 1. Overall Theme - Deep Dark */
    .stApp { background-color: #020617 !important; color: #F8FAFC !important; }
    
    /* 2. Navigation Styling (Single Row, High Contrast) */
    div[data-testid="stSegmentedControl"] { 
        display: flex !important; 
        flex-direction: row !important;
        justify-content: flex-end !important; 
        margin-top: -65px !important; 
        gap: 5px !important;
        background: transparent !important;
    }
    div[data-testid="stSegmentedControl"] button {
        background-color: #1E293B !important; 
        color: #38BDF8 !important; /* BLUE/CYAN TEXT */
        border: 1px solid #334155 !important;
        font-size: 11px !important;
        font-weight: 800 !important;
        padding: 8px 15px !important;
        min-width: 135px !important;
        text-transform: uppercase;
    }
    /* Selected Button: Black text on Cyan background */
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background-color: #38BDF8 !important; 
        color: #000000 !important; 
        border: 1px solid #38BDF8 !important;
    }

    /* 3. Custom KPI Card (Forced Wrapping) */
    .kpi-card {
        background-color: #0F172A;
        border: 1px solid #1E293B;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 10px;
    }
    .kpi-label {
        font-size: 10px;
        color: #94A3B8;
        font-weight: 700;
        text-transform: uppercase;
        line-height: 1.3;
        margin-bottom: 8px;
        white-space: normal !important; /* Force Wrapping */
        word-wrap: break-word !important;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: 800;
        color: #38BDF8;
    }
    .kpi-perc {
        font-size: 11px;
        color: #64748B;
        margin-top: 4px;
    }

    /* 4. Table and Header Adjustments */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { font-size: 11px !important; }
    h1 { color: #F8FAFC; font-size: 20px !important; letter-spacing: 0.5px; }
    h3 { font-size: 0.85rem !important; color: #38BDF8; margin-top: 20px; text-transform: uppercase; font-weight: 700; }
    hr { border-top: 1px solid #1E293B; }
    </style>
    """, unsafe_allow_html=True)

# Function to render the custom KPI card
def render_kpi(label, value, percentage=None):
    perc_html = f"<div class='kpi-perc'>{percentage} Staff</div>" if percentage else ""
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value:,}</div>
            {perc_html}
        </div>
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
        snipe_final = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(snipe_final, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_final = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_final, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # --- LOGIC: EXCLUDE HEADTEACHERS FROM EXCESSIVE DEVICES ---
        excessive_mask = (df['AssignedCount'] > 1) & (~df['Job Title'].str.contains('Headteacher', case=False, na=False))
        
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
            "More Than Allowed": df[excessive_mask].copy(), # Headteachers excluded here
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

# --- HEADER & NAVIGATION ---
h1, h2 = st.columns([2.2, 1.8])
with h1:
    st.title("JIGAWAUNITE:: E-INK Digital Audit")
with h2:
    view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

st.write("---")

data, summary = generate_audit_data()

if data is not None:
    total_pop = summary["Total Staff"]

    if view == "📊 SUMMARY":
        c1, c2 = st.columns(2)
        with c1: render_kpi("TOTAL ACTIVE STAFF", summary["Total Staff"])
        with c2: render_kpi("TOTAL TABLETS ASSIGNED", summary["Total Assigned"])
        
        st.write("### NON-COMPLIANCE SUMMARY")
        m = st.columns(5)
        
        def kpi_box(col, label, df):
            count = len(df)
            perc = f"{(count / total_pop) * 100:.1f}%" if total_pop > 0 else "0%"
            with col: render_kpi(label, count, perc)

        kpi_box(m[0], "STAFF WITHOUT ASSIGNED TABLET", summary["No Tablet"])
        kpi_box(m[1], "STAFF WITH EXCESSIVE DEVICES THAN ALLOWED", summary["More Than Allowed"])
        kpi_box(m[2], "STAFF ASSIGNED TABLET BUT NOT USING IT", summary["Not Using"])
        kpi_box(m[3], "STAFF USING OTHERS' TABLETS", summary["Assigned Others"])
        kpi_box(m[4], "STAFF LOGGING INTO MULTIPLE DEVICES", summary["Multiple Devices"])

    elif view == "📋 BREAKDOWN":
        breakdown_cols = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'County', 'Job Title', 'Tablet ID Assigned', 'AssignedCount', 'Tablet ID Used', 'UsedCount', 'Matches SnipeIT?']
        st.dataframe(data[breakdown_cols], use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        base = ['EmployeeID', 'Employee Name', 'Job Title']
        comment = ['Admin Comments / Resolution']

        e1, e2 = st.columns(2)
        with e1:
            st.write("### STAFF WITHOUT ASSIGNED TABLET")
            st.data_editor(summary["No Tablet"][base + comment], use_container_width=True, hide_index=True, key="x1")
        with e2:
            st.write("### STAFF WITH EXCESSIVE DEVICES THAN ALLOWED (EXCL. HEADTEACHERS)")
            st.data_editor(summary["More Than Allowed"][base + ['Tablet ID Assigned', 'AssignedCount'] + comment], use_container_width=True, hide_index=True, key="x2")
        
        st.write("---")
        e3, e4 = st.columns(2)
        with e3:
            st.write("### STAFF ASSIGNED TABLET BUT NOT USING IT")
            st.data_editor(summary["Not Using"][base + ['Tablet ID Assigned', 'Tablet ID Used'] + comment], use_container_width=True, hide_index=True, key="x3")
        with e4:
            st.write("### STAFF USING OTHERS' TABLETS")
            st.data_editor(summary["Assigned Others"][base + ['Tablet ID Assigned', 'Tablet ID Used'] + comment], use_container_width=True, hide_index=True, key="x4")
            
