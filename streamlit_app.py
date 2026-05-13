import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME REPAIR: ELIMINATING WHITE BACKGROUNDS ---
def apply_view_theme(view_name):
    themes = {
        "📊 SUMMARY": "#000000",
        "📋 BREAKDOWN": "#020617",
        "🚨 ESCALATION": "#111827"
    }
    bg = themes.get(view_name, "#000000")
    
    st.markdown(f"""
        <style>
        /* Main App Background */
        .stApp {{ background-color: {bg} !important; color: #F8FAFC !important; }}
        
        /* Navigation Styling - REMOVING WHITE BACKGROUND */
        div[data-testid="stSegmentedControl"] {{ 
            display: flex !important; 
            justify-content: flex-end !important; 
            margin-top: -65px !important; 
            background-color: transparent !important;
        }}

        /* Individual Button Styling */
        div[data-testid="stSegmentedControl"] button {{
            background-color: rgba(30, 41, 59, 0.5) !important; /* Semi-transparent dark blue */
            color: #38BDF8 !important; /* Bright Blue Text */
            border: 1px solid #334155 !important;
            font-weight: 800 !important;
            min-width: 140px !important;
            transition: all 0.3s ease;
        }}

        /* Hover State */
        div[data-testid="stSegmentedControl"] button:hover {{
            border-color: #38BDF8 !important;
            background-color: rgba(56, 189, 248, 0.1) !important;
        }}

        /* Active/Selected Button - NO WHITE BACKGROUND */
        div[data-testid="stSegmentedControl"] button[aria-checked="true"] {{
            background-color: #38BDF8 !important; /* Solid Cyan */
            color: #000000 !important; /* Black text for high contrast */
            border: 1px solid #38BDF8 !important;
            box-shadow: 0px 0px 15px rgba(56, 189, 248, 0.4);
        }}

        /* KPI Card Styling */
        .kpi-card {{
            background-color: #0F172A;
            border: 1px solid #1E293B;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            min-height: 160px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .kpi-label {{
            font-size: 11px;
            color: #94A3B8;
            font-weight: 700;
            text-transform: uppercase;
            white-space: normal !important;
            line-height: 1.4;
            margin-bottom: 10px;
        }}
        .kpi-value {{ font-size: 28px; font-weight: 800; color: #38BDF8; }}
        
        /* General Text Visibility */
        p, span, label {{ color: #F8FAFC !important; }}
        </style>
    """, unsafe_allow_html=True)

@st.cache_data
def generate_audit_data():
    try:
        # Placeholder for data loading - replace with actual file paths
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # Merging SnipeIT Data
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        snipe_df = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(snipe_df, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        # Merging Geolocation Data
        geo_df = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_df, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # HEADTEACHER EXCLUSION LOGIC
        excessive_mask = (df['AssignedCount'] > 1) & (df['Job Title'].str.upper() != 'HEADTEACHER')
        
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set = set([s.strip() for s in assigned.split(',')])
            u_set = set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)
        
        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": snipe_counts['AssignedCount'].sum(),
            "No Tablet": df[df['AssignedCount'] == 0].copy(),
            "More Than Allowed": df[excessive_mask].copy(), # Headteachers Excluded
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- NAV BAR ---
h1, h2 = st.columns([2.2, 1.8])
with h1: st.title("JIGAWAUNITE:: E-INK Audit")
with h2: view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

apply_view_theme(view)
st.write("---")

data, summary = generate_audit_data()

if data is not None:
    total_pop = summary["Total Staff"]

    if view == "📊 SUMMARY":
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">TOTAL ACTIVE STAFF</div><div class="kpi-value">{summary["Total Staff"]:,}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">TOTAL TABLETS ASSIGNED</div><div class="kpi-value">{summary["Total Assigned"]:,}</div></div>', unsafe_allow_html=True)
        
        st.write("### NON-COMPLIANCE SUMMARY")
        m = st.columns(5)
        labels = ["STAFF WITHOUT ASSIGNED TABLET", "STAFF WITH EXCESSIVE DEVICES THAN ALLOWED", "STAFF ASSIGNED TABLET BUT NOT USING IT", "STAFF USING OTHERS' TABLETS", "STAFF LOGGING INTO MULTIPLE DEVICES"]
        keys = ["No Tablet", "More Than Allowed", "Not Using", "Assigned Others", "Multiple Devices"]
        
        for i, col in enumerate(m):
            count = len(summary[keys[i]])
            perc = f"{(count / total_pop) * 100:.1f}%"
            with col:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{labels[i]}</div><div class="kpi-value">{count}</div><div style="font-size:11px; color:#64748B;">{perc} Staff</div></div>', unsafe_allow_html=True)

    elif view == "📋 BREAKDOWN":
        cols = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'County', 'Job Title', 'Phone Number', 'Tablet ID Assigned', 'AssignedCount', 'Tablet ID Used', 'UsedCount', 'Matches SnipeIT?']
        st.dataframe(data[cols], use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        base = ['EmployeeID', 'Employee Name', 'Job Title']
        
        st.write("### STAFF WITHOUT ASSIGNED TABLET")
        st.data_editor(summary["No Tablet"][base], use_container_width=True, hide_index=True)
        
        st.write("### STAFF WITH EXCESSIVE DEVICES THAN ALLOWED (EXCL. HEADTEACHERS)")
        st.data_editor(summary["More Than Allowed"][base + ['Tablet ID Assigned', 'AssignedCount']], use_container_width=True, hide_index=True)
