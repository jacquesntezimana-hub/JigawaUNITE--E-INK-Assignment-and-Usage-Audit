import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME: YOUR ORIGINAL CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #020617 !important; color: #F8FAFC !important; }
    
    div[data-testid="stSegmentedControl"] { 
        display: flex !important; 
        flex-direction: row !important;
        justify-content: flex-end !important; 
        margin-top: -65px !important; 
        gap: 5px !important;
    }
    div[data-testid="stSegmentedControl"] button {
        background-color: #1E293B !important; 
        color: #F8FAFC !important; 
        border: 1px solid #334155 !important;
        font-size: 11px !important;
        padding: 8px 15px !important;
        min-width: 130px !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background-color: #38BDF8 !important; 
        color: #020617 !important; 
    }

    .kpi-card {
        background-color: #0F172A;
        border: 1px solid #1E293B;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        margin-bottom: 10px;
    }
    .kpi-label {
        font-size: 11px;
        color: #94A3B8;
        font-weight: 600;
        text-transform: uppercase;
        line-height: 1.3;
        margin-bottom: 8px;
        word-wrap: break-word;
        white-space: normal; 
    }
    .kpi-value { font-size: 24px; font-weight: 700; color: #38BDF8; }
    .kpi-perc { font-size: 12px; color: #64748B; margin-top: 4px; }

    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { font-size: 11px !important; }
    h1 { color: #F8FAFC; font-size: 20px !important; letter-spacing: 0.5px; }
    h3 { font-size: 0.9rem !important; color: #38BDF8; margin-top: 20px; text-transform: uppercase; font-weight: 700; }
    hr { border-top: 1px solid #1E293B; }
    </style>
    """, unsafe_allow_html=True)

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
        snipe_agg = snipe.groupby('JOIN_ID').agg({snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_merged = pd.merge(snipe_agg, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_agg = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_merged = pd.merge(geo_agg, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_merged, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_merged, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # --- THE SPECIFIC HEADTEACHER COMPLIANCE RULE ---
        def audit_logic(row):
            title = str(row['Job Title']).upper()
            count = row['AssignedCount']
            is_ht = "HEAD TEACHER" in title or "HEADTEACHER" in title
            
            # Non-compliance: More than expected (HT > 2, others > 1)
            excessive = (count > 2) if is_ht else (count > 1)
            # Non-compliance: Less than expected (HT < 2, others == 0)
            missing = (count < 2) if is_ht else (count == 0)
            
            return pd.Series([excessive, missing])

        df[['Flag_Excessive', 'Flag_Missing']] = df.apply(audit_logic, axis=1)

        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set([s.strip() for s in assigned.split(',')]), set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")
        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": int(snipe_counts['AssignedCount'].sum()),
            "No Tablet": df[df['Flag_Missing'] == True].copy(), 
            "More Than Allowed": df[df['Flag_Excessive'] == True].copy(), 
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
with h1: st.title("JIGAWAUNITE:: E-INK Assignment and Usage Digital Audit")
with h2: view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

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
        
        kpi_list = [
            ("STAFF WITHOUT ASSIGNED TABLET", summary["No Tablet"]),
            ("STAFF WITH EXCESSIVE DEVICES THAN ALLOWED", summary["More Than Allowed"]),
            ("STAFF ASSIGNED TABLET BUT NOT USING IT", summary["Not Using"]),
            ("STAFF USING OTHERS' TABLETS", summary["Assigned Others"]),
            ("STAFF LOGING INTO MULTIPLE DEVICES", summary["Multiple Devices"])
        ]
        
        for i, (label, df) in enumerate(kpi_list):
            count = len(df)
            perc = f"{(count / total_pop) * 100:.1f}%" if total_pop > 0 else "0%"
            with m[i]: render_kpi(label, count, perc)

    elif view == "📋 BREAKDOWN":
        st.dataframe(data, use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        base = ['EmployeeID', 'Employee Name', 'Job Title']
        comment = ['Admin Comments / Resolution']
        
        st.write("### STAFF WITH EXCESSIVE DEVICES THAN ALLOWED")
        st.data_editor(summary["More Than Allowed"][base + ['AssignedCount'] + comment], use_container_width=True, hide_index=True, key="esc_e")
        st.write("---")
        st.write("### STAFF WITHOUT ASSIGNED TABLET (INC. HTs WITH < 2)")
        st.data_editor(summary["No Tablet"][base + ['AssignedCount'] + comment], use_container_width=True, hide_index=True, key="esc_m")
