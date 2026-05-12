import streamlit as st
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="NewGlobe · JigawaUNITE", layout="wide")

# Custom CSS for NewGlobe Style and Right-Aligned Navigation
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: bold; }
    .stSegmentedControl {
        display: flex;
        justify-content: flex-end;
    }
    div[data-testid="stSegmentedControl"] button {
        min-width: 120px;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def generate_audit_data():
    try:
        # Load Local Files
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
        snipe_grouped = snipe.groupby('JOIN_ID').agg({
            snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID').rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        geo_grouped = geo.groupby('JOIN_ID').agg({
            'Device Serial': lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID').rename(columns={'Device Serial': 'Tablet ID Used'})

        # Final Merge
        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        df['Number of EINK Tablet Assigned'] = df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        df['Count Unique Devices Logged In'] = df['Count Unique Devices Logged In'].fillna(0).astype(int)
        
        # Match Logic
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            if assigned in ['nan', ''] or used in ['nan', '']: return "No Data"
            a_set, u_set = set([s.strip() for s in assigned.split(',')]), set([s.strip() for s in used.split(',')])
            return "Yes" if a_set == u_set else ("Partial Match" if not a_set.isdisjoint(u_set) else "No")

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # SPECIAL LOGIC: Filter for "Staff assigned more tablets than allowed"
        # 1. Start with anyone who has > 1 tablet
        over_assigned_mask = df['Number of EINK Tablet Assigned'] > 1
        
        # 2. Identify Headteachers
        # Checks if "headteacher" or "head teacher" is in the Job Title string
        is_headteacher = df['Job Title'].str.contains('headteacher|head teacher', case=False, na=False)
        
        # 3. Exclude Headteachers if they have exactly 2 tablets
        exclude_ht = is_headteacher & (df['Number of EINK Tablet Assigned'] == 2)
        
        # Apply the exclusion
        over_assigned_df = df[over_assigned_mask & ~exclude_ht]

        summary_vals = {
            "Total Staff": len(active),
            "Total Assigned": snipe_counts['Number of EINK Tablet Assigned'].sum(),
            "No Tablet": df[df['Number of EINK Tablet Assigned'] == 0],
            "More Than Allowed": over_assigned_df,
            "Not Using": df[(df['Number of EINK Tablet Assigned'] > 0) & (df['Count Unique Devices Logged In'] == 0)],
            "Assigned Others": df[df['Matches SnipeIT?'] == "No"],
            "Multiple Devices": df[df['Count Unique Devices Logged In'] > 1]
        }
        return df, summary_vals
    except Exception as e:
        st.error(f"Data Error: {e}")
        return None, None

# --- HEADER ---
h1, h2 = st.columns([1, 1])
with h1:
    st.title("NewGlobe · JigawaUNITE")
with h2:
    view = st.segmented_control(
        "Navigation", 
        options=["📊 Summary", "📋 Breakdown", "🚨 Escalation"], 
        selection_mode="single", 
        default="📊 Summary",
        label_visibility="collapsed"
    )

st.write("---")

audit_df, summary = generate_audit_data()

if audit_df is not None:
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
        st.subheader("Detailed Audit Breakdown")
        cols = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'Job Title', 'Tablet ID Assigned', 'Number of EINK Tablet Assigned', 'Tablet ID Used', 'Count Unique Devices Logged In', 'Matches SnipeIT?']
        st.dataframe(audit_df[cols], use_container_width=True, hide_index=True)

    elif view == "🚨 Escalation":
        st.header("🚨 Priority Escalation Action Lists")
        common = ['EmployeeID', 'Employee Name', 'Current Academy Code', 'Job Title']

        with st.expander("1. Staff without assigned tablet", expanded=True):
            st.dataframe(summary["No Tablet"][common], use_container_width=True, hide_index=True)

        with st.expander("2. Staff assigned more tablets than allowed (Excl. HT with 2)", expanded=True):
            st.info("💡 Note: Headteachers with exactly 2 tablets are authorized and excluded from this list.")
            st.dataframe(summary["More Than Allowed"][common + ['Tablet ID Assigned', 'Number of EINK Tablet Assigned']], use_container_width=True, hide_index=True)

        with st.expander("3. Staff assigned tablet but not using/log in it", expanded=True):
            st.dataframe(summary["Not Using"][common + ['Tablet ID Assigned']], use_container_width=True, hide_index=True)

        with st.expander("4. Staff using tablets assigned to others", expanded=True):
            st.dataframe(summary["Assigned Others"][common + ['Tablet ID Assigned', 'Tablet ID Used']], use_container_width=True, hide_index=True)

        with st.expander("5. Staff logging into multiple devices", expanded=True):
            st.dataframe(summary["Multiple Devices"][common + ['Tablet ID Used', 'Count Unique Devices Logged In']], use_container_width=True, hide_index=True)
