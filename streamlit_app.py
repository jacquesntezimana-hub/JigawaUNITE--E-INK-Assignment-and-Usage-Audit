import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME REPAIR ---
def apply_view_theme(view_name):
    # Mapping distinct, high-visibility backgrounds
    themes = {
        "📊 SUMMARY": "#000000",      # Pure Black
        "📋 BREAKDOWN": "#020617",    # Dark Navy 
        "🚨 ESCALATION": "#111827"    # Deep Charcoal
    }
    bg = themes.get(view_name, "#000000")
    
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {bg} !important; color: #F8FAFC !important; }}
        
        /* Navigation Row */
        div[data-testid="stSegmentedControl"] {{ 
            display: flex !important; 
            justify-content: flex-end !important; 
            margin-top: -65px !important; 
        }}

        /* Button Visibility: Black text on Cyan when active, Blue text when inactive */
        div[data-testid="stSegmentedControl"] button {{
            background-color: #1E293B !important; 
            color: #38BDF8 !important; 
            font-weight: 800 !important;
            min-width: 130px !important;
        }}
        div[data-testid="stSegmentedControl"] button[aria-checked="true"] {{
            background-color: #38BDF8 !important; 
            color: #000000 !important; 
        }}

        /* KPI Card Wrapping Fix */
        .kpi-card {{
            background-color: #0F172A;
            border: 1px solid #1E293B;
            padding: 15px;
            border-radius: 8px;
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
            word-wrap: break-word !important;
            line-height: 1.4;
            margin-bottom: 10px;
        }}
        .kpi-value {{ font-size: 26px; font-weight: 800; color: #38BDF8; }}
        
        /* Table Visibility */
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ font-size: 11px !important; }}
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
        snipe_df = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_final = pd.merge(snipe_df, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_df = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_final = pd.merge(geo_df, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # Headteacher Exclusion Logic for Excessive Devices
        # Only flag if AssignedCount > 1 AND Job Title is NOT Headteacher
        excessive_mask = (df['AssignedCount'] > 1) & (df['Job Title'].str.upper() != 'HEADTEACHER')
        
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
            "More Than Allowed": df[excessive_mask].copy(), # Headteachers Excluded Here
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"].copy(),
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- NAV ---
h1, h2 = st.columns([2.2, 1.8])
with h1: st.title("JIGAWAUNITE:: E-INK Assignment and Usage Digital Audit")
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
        labels = [
            "STAFF WITHOUT ASSIGNED TABLET", 
            "STAFF WITH EXCESSIVE DEVICES THAN ALLOWED", 
            "STAFF ASSIGNED TABLET BUT NOT USING IT", 
            "STAFF USING OTHERS' TABLETS", 
            "STAFF LOGING INTO MULTIPLE DEVICES"
        ]
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
        for key in summary:
            if isinstance(summary[key], pd.DataFrame): summary[key]["Admin Comments"] = ""
        
        e1, e2 = st.columns(2)
        with e1:
            st.write("### STAFF WITHOUT ASSIGNED TABLET")
            st.data_editor(summary["No Tablet"][base + ["Admin Comments"]], use_container_width=True, hide_index=True)
        with e2:
            st.write("### STAFF WITH EXCESSIVE DEVICES THAN ALLOWED (EXCL. HEADTEACHERS)")
            st.data_editor(summary["More Than Allowed"][base + ['Tablet ID Assigned', 'AssignedCount', "Admin Comments"]], use_container_width=True, hide_index=True)
        
        st.write("---")
        e3, e4 = st.columns(2)
        with e3:
            st.write("### STAFF ASSIGNED TABLET BUT NOT USING IT")
            st.data_editor(summary["Not Using"][base + ['Tablet ID Assigned', "Admin Comments"]], use_container_width=True, hide_index=True)
        with e4:
            st.write("### STAFF USING OTHERS' TABLETS")
            st.data_editor(summary["Assigned Others"][base + ['Tablet ID Assigned', 'Tablet ID Used', "Admin Comments"]], use_container_width=True, hide_index=True)
