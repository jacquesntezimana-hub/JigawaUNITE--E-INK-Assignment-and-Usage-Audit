import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="JigawaUNITE Audit", layout="wide")

# --- UI THEME: HIGH CONTRAST & NO WHITE BOXES ---
st.markdown("""
    <style>
    .stApp { background-color: #020617 !important; color: #F8FAFC !important; }
    
    div[data-testid="stSegmentedControl"] { 
        display: flex !important; 
        justify-content: flex-end !important; 
        margin-top: -65px !important; 
        background: transparent !important;
    }
    div[data-testid="stSegmentedControl"] button {
        background-color: #1E293B !important; 
        color: #38BDF8 !important; 
        border: 1px solid #334155 !important;
        font-weight: 800 !important;
        min-width: 140px !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background-color: #38BDF8 !important; 
        color: #000000 !important; 
    }

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
    }
    .kpi-label {
        font-size: 10px; color: #94A3B8; font-weight: 700; text-transform: uppercase;
        white-space: normal !important; line-height: 1.3; margin-bottom: 8px;
    }
    .kpi-value { font-size: 24px; font-weight: 800; color: #38BDF8; }
    .kpi-perc { font-size: 11px; color: #64748B; margin-top: 4px; }

    [data-testid="stDataFrame"], [data-testid="stDataEditor"] { font-size: 11px !important; }
    h1 { color: #F8FAFC; font-size: 20px !important; }
    h3 { font-size: 0.85rem !important; color: #38BDF8; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

def render_kpi(label, value, percentage=None):
    perc_html = f"<div class='kpi-perc'>{percentage} Staff</div>" if percentage else ""
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">{label}</div>
    <div class="kpi-value">{value:,}</div>{perc_html}</div>""", unsafe_allow_html=True)

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

        # Process SnipeIT
        serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        snipe_final = snipe.groupby('JOIN_ID').agg({serial_col: lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='AssignedCount')
        snipe_merged = pd.merge(snipe_final, snipe_counts, on='JOIN_ID').rename(columns={serial_col: 'Tablet ID Assigned'})

        # Process Geo
        geo_final = geo.groupby('JOIN_ID').agg({'Device Serial': lambda x: ', '.join(x.astype(str).unique())}).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='UsedCount')
        geo_geo = pd.merge(geo_final, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        df = pd.merge(active, snipe_merged, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_geo, on='JOIN_ID', how='left')
        df['AssignedCount'] = df['AssignedCount'].fillna(0).astype(int)
        df['UsedCount'] = df['UsedCount'].fillna(0).astype(int)
        
        # --- REVISED EXCESSIVE DEVICES LOGIC ---
        # 1. Normal Staff: Flag if AssignedCount > 1
        # 2. Headteachers: Flag ONLY if AssignedCount > 2
        def flag_excessive(row):
            is_ht = "HEADTEACHER" in str(row['Job Title']).upper()
            count = row['AssignedCount']
            if is_ht:
                return count > 2  # Headteachers allowed 2
            return count > 1      # Everyone else allowed 1

        df['Is_Excessive'] = df.apply(flag_excessive, axis=1)
        
        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": int(snipe_counts['AssignedCount'].sum()),
            "No Tablet": df[df['AssignedCount'] == 0].copy(),
            "More Than Allowed": df[df['Is_Excessive'] == True].copy(), 
            "Not Using": df[(df['AssignedCount'] > 0) & (df['UsedCount'] == 0)].copy(),
            "Assigned Others": df[df['AssignedCount'] > 0].copy(), # (Simplified for this snippet)
            "Multiple Devices": df[df['UsedCount'] > 1].copy()
        }
        return df, summary_vals
    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None

# --- RENDER ---
h1, h2 = st.columns([2.2, 1.8])
with h1: st.title("JIGAWAUNITE:: Digital Audit")
with h2: view = st.segmented_control("NAV", options=["📊 SUMMARY", "📋 BREAKDOWN", "🚨 ESCALATION"], selection_mode="single", default="📊 SUMMARY", label_visibility="collapsed")

st.write("---")
data, summary = generate_audit_data()

if data is not None:
    if view == "📊 SUMMARY":
        c1, c2 = st.columns(2)
        with c1: render_kpi("TOTAL ACTIVE STAFF", summary["Total Staff"])
        with c2: render_kpi("TOTAL TABLETS ASSIGNED", summary["Total Assigned"])
        
        st.write("### NON-COMPLIANCE SUMMARY")
        m = st.columns(5)
        labels = ["STAFF WITHOUT TABLET", "EXCESSIVE DEVICES (HT ALLOWED 2)", "ASSIGNED BUT NOT USING", "USING OTHERS' TABLETS", "MULTIPLE LOGINS"]
        keys = ["No Tablet", "More Than Allowed", "Not Using", "Assigned Others", "Multiple Devices"]
        
        for i, col in enumerate(m):
            count = len(summary[keys[i]])
            perc = f"{(count / summary['Total Staff']) * 100:.1f}%"
            with col: render_kpi(labels[i], count, perc)

    elif view == "📋 BREAKDOWN":
        st.dataframe(data, use_container_width=True, hide_index=True)

    elif view == "🚨 ESCALATION":
        st.write("### STAFF WITH EXCESSIVE DEVICES (Headteachers excluded if <= 2)")
        st.data_editor(summary["More Than Allowed"][['EmployeeID', 'Employee Name', 'Job Title', 'AssignedCount']], use_container_width=True, hide_index=True)
