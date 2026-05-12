import streamlit as st
import pandas as pd

st.set_page_config(page_title="Jigawa Audit Report", layout="wide")
st.title("📊 Final Integrated Audit Report")

@st.cache_data
def generate_jigawa_audit():
    try:
        # 1. Load the 3 source files
        active = pd.read_excel("Active Staff.xlsx")
        snipe = pd.read_excel("Snipe_IT.xlsx")
        geo = pd.read_excel("Geolocation Sync 07_10 Apr.xlsx")

        # Clean column names
        active.columns = active.columns.str.strip()
        snipe.columns = snipe.columns.str.strip()
        geo.columns = geo.columns.str.strip()

        # 2. Standardize Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # 3. Find the Serial column in Snipe IT (flexible search)
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        # 4. AGGREGATE SNIPE IT (Tablets Assigned)
        # Combine serials and count total tablets
        snipe_grouped = snipe.groupby('JOIN_ID').agg({
            snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        
        # Add the count
        snipe_counts = snipe.groupby('JOIN_ID').size().reset_index(name='Number of EINK Tablet Assigned')
        snipe_final = pd.merge(snipe_grouped, snipe_counts, on='JOIN_ID')
        
        # RENAME AS REQUESTED
        snipe_final = snipe_final.rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        # 5. AGGREGATE GEOLOCATION (Tablets Used)
        # Combine used serials and count unique devices
        geo_grouped = geo.groupby('JOIN_ID').agg({
            'Device Serial': lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID')
        
        # RENAME AS REQUESTED
        geo_final = geo_final.rename(columns={'Device Serial': 'Tablet ID Used'})

        # 6. MERGE ALL TOGETHER
        # Left join on Active Staff keeps everyone in payroll
        df = pd.merge(active, snipe_final, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        # 7. LOGIC: Matches SnipeIT?
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            
            if assigned in ['nan', 'none', ''] or used in ['nan', 'none', '']:
                return "No Data"
            
            # Split strings back to sets to compare them
            assigned_set = set([s.strip() for s in assigned.split(',')])
            used_set = set([s.strip() for s in used.split(',')])
            
            if assigned_set == used_set:
                return "Yes"
            elif not assigned_set.isdisjoint(used_set):
                return "Partial Match"
            else:
                return "No"

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 8. FINAL OUTPUT SELECTION (The 9 Columns)
        output_columns = [
            'EmployeeID',
            'Employee Name',
            'Current Academy Code',
            'Job Title',
            'Tablet ID Assigned',
            'Number of EINK Tablet Assigned',
            'Tablet ID Used',
            'Count Unique Devices Logged In',
            'Matches SnipeIT?'
        ]

        # Ensure columns exist and fill empty counts with 0
        final_df = df[output_columns].copy()
        final_df['Number of EINK Tablet Assigned'] = final_df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        final_df['Count Unique Devices Logged In'] = final_df['Count Unique Devices Logged In'].fillna(0).astype(int)
        
        return final_df

    except Exception as e:
        st.error(f"Critical Error: {e}")
        return None

# --- UI ---
report_data = generate_jigawa_audit()

if report_data is not None:
    st.dataframe(report_data, use_container_width=True)
    
    # Export Button
    csv = report_data.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Full Audit Report (CSV)", csv, "Jigawa_Audit_Final.csv", "text/csv")
