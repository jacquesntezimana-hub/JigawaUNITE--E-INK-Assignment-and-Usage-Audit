import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME REPAIR: NO WHITE BACKGROUNDS, HIGH VISIBILITY ---
def apply_view_theme(view_name):
    themes = {
        "📊 SUMMARY": "#000000",
        "📋 BREAKDOWN": "#020617",
        "🚨 ESCALATION": "#111827"
    }
    bg = themes.get(view_name, "#000000")
    
    st.markdown(f"""
        <style>
        /* Force Deep Dark Background */
        .stApp {{ background-color: {bg} !important; color: #F8FAFC !important; }}
        
        /* Navigation Styling: Transparent background, no white boxes */
        div[data-testid="stSegmentedControl"] {{ 
            display: flex !important; 
            justify-content: flex-end !important; 
            margin-top: -65px !important; 
            background-color: transparent !important;
        }}

        /* Button Styling */
        div[data-testid="stSegmentedControl"] button {{
            background-color: #1E293B !important; /* Slate Dark Blue */
            color: #38BDF8 !important; /* Cyan-Blue Text */
            border: 1px solid #334155 !important;
            font-weight: 800 !important;
            min-width: 150px !important;
            text-transform: uppercase;
        }}

        /* Active Button Highlight: Solid Cyan with Black Text */
        div[data-testid="stSegmentedControl"] button[aria-checked="true"] {{
            background-color: #38BDF8 !important; 
            color: #000000 !important; 
            border: 1px solid #38BDF8 !important;
        }}

        /* KPI Card Styling with Forced Text Wrap */
        .kpi-card {{
            background-color: #0F172A;
            border: 1px solid #1E293B;
            padding: 15px;
            border-radius: 10px;
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
            white-space: normal !important; /* Forces Text Wrapping */
            line-height: 1.4;
            margin-bottom: 10px;
        }}
        .kpi-value {{ font-size: 26px; font-weight: 800; color: #38BDF8; }}
        
        /* Ensure DataFrames are readable */
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ font-size: 11px !important; }}
        h3 {{ color: #38BDF8; font-size: 0.9rem !important; margin-top: 20px; }}
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

        # SnipeIT Merge
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        s_grouped = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        s_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(s_grouped, s_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        # Geolocation Merge
        geo_grouped = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # --- LOGIC: EXCLUDE HEADTEACHERS FROM EXCESSIVE DEVICES ---
        # Flag only if count > 1 AND job title is not 'Headteacher'
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
            "More Than Allowed": df[excessive_mask].copy(), # Excludes Headteachers
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- UI RENDER ---
h1, h2 = st.columns([2.2, 1.8])
with h1: st.title("JIGAWAUNITE:: E-INK Digital Audit")
with h2: view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

apply_view_theme(view)
st.write("---")

data, summary = generate_audit_data()

if data is not None:
    total_pop = summary["Total Staff"]

    if view == "📊 SUMMARY":
        # Row 1: Totals
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="kpi-card"><div class="kpi-label">TOTAL ACTIVE STAFF</div><div class="kpi-value">{summary["Total Staff"]:,}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="kpi-card"><div class="kpi-label">TOTAL TABLETS ASSIGNED</div><div class="kpi-value">{summary["Total Assigned"]:,}</div></div>', unsafe_allow_html=True)
        
        # Row 2: Non-Compliance
        st.write("### NON-COMPLIANCE SUMMARY")
        m = st.columns(5)
        labels = ["STAFF WITHOUT ASSIGNED TABLET", "STAFF WITH EXCESSIVE DEVICES THAN ALLOWED", "STAFF ASSIGNED TABLET BUT NOT USING IT", "STAFF USING OTHERS' TABLETS", "STAFF LOGING INTO MULTIPLE DEVICES"]
        keys = ["No Tablet", "More Than Allowed", "Not Using", "Assigned Others", "Multiple Devices"]
        
        for i, col in enumerate(m):
            count = len(summary[keys[i]])
            perc = f"{(count / total_pop) * 100:.1f}%"
            with col:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{labels[i]}</div><div class="kpi-value">{count}</div><div style="font-size:11px; color:#64748B;">{perc} Staff</div></div>', unsafe_allow_html=True)

    elif view == "📋 BREAKDOWN":
        cols = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'County', 'Job Title', 'Tablet ID Assigned', 'AssignedCount', 'Tablet ID Used', 'UsedCount', 'Matches SnipeIT?']
        st.dataframe(data[cols], use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        base = ['EmployeeID', 'Employee Name', 'Job Title']
        st.write("### STAFF WITHOUT ASSIGNED TABLET")
        st.data_editor(summary["No Tablet"][base], use_container_width=True, hide_index=True)
        
        st.write("### STAFF WITH EXCESSIVE DEVICES THAN ALLOWED (EXCLUDES HEADTEACHERS)")
        st.data_editor(summary["More Than Allowed"][base + ['AssignedCount']], use_container_width=True, hide_index=True)
