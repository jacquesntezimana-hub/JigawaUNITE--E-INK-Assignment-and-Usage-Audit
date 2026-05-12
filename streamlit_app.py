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

        # Clean all column names
        for df in [active, snipe, geo]:
            df.columns = df.columns.str.strip()

        # 2. Standardize Join Keys
        active['JOIN_ID'] = active['EmployeeID'].astype(str).str.strip()
        snipe['JOIN_ID'] = snipe['Username'].astype(str).str.strip()
        geo['JOIN_ID'] = geo['Employee Id'].astype(str).str.strip()

        # 3. IDENTIFY SERIAL COLUMNS
        snipe_serial_col = next((c for c in snipe.columns if 'SERIAL' in c.upper()), None)
        
        # 4. AGGREGATION LOGIC (Handling multiple serials per teacher)
        
        # A. Snipe_IT: Count tablets AND join serial numbers with a comma
        snipe_grouped = snipe.groupby('JOIN_ID').agg({
            snipe_serial_col: lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        snipe_grouped['Number of EINK Tablet Assigned'] = snipe.groupby('JOIN_ID').size().values
        snipe_grouped = snipe_grouped.rename(columns={snipe_serial_col: 'Tablet ID Assigned'})

        # B. Geolocation: Count unique devices AND join serial numbers with a comma
        geo_grouped = geo.groupby('JOIN_ID').agg({
            'Device Serial': lambda x: ', '.join(x.astype(str).unique())
        }).reset_index()
        # Calculate unique count
        geo_counts = geo.groupby('JOIN_ID')['Device Serial'].nunique().reset_index(name='Count Unique Devices Logged In')
        geo_final = pd.merge(geo_grouped, geo_counts, on='JOIN_ID')
        geo_final = geo_final.rename(columns={'Device Serial': 'Tablet ID Used'})

        # 5. PERFORM MERGES (Left Join)
        df = pd.merge(active, snipe_grouped, on='JOIN_ID', how='left')
        df = pd.merge(df, geo_final, on='JOIN_ID', how='left')

        # 6. LOGIC: Matches SnipeIT?
        def check_match(row):
            assigned = str(row.get('Tablet ID Assigned', '')).strip().lower()
            used = str(row.get('Tablet ID Used', '')).strip().lower()
            
            if assigned in ['nan', 'none', ''] or used in ['nan', 'none', '']:
                return "No Data"
            
            # If multiple serials, we check if there is any overlap
            assigned_list = set(assigned.split(', '))
            used_list = set(used.split(', '))
            
            if assigned_list == used_list:
                return "Yes"
            elif assigned_list.intersection(used_list):
                return "Partial Match"
            else:
                return "No"

        df['Matches SnipeIT?'] = df.apply(check_match, axis=1)

        # 7. FINAL COLUMN SELECTION
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

        # Final Formatting
        final_df = df[output_columns].copy()
        final_df['Number of EINK Tablet Assigned'] = final_df['Number of EINK Tablet Assigned'].fillna(0).astype(int)
        final_df['Count Unique Devices Logged In'] = final_df['Count Unique Devices Logged In'].fillna(0).astype(int)

        return final_df

    except Exception as e:
        st.error(f"Mapping Error: {e}")
        return None

# --- DISPLAY ---
report_df = generate_jigawa_audit()

if report_df is not None:
    st.dataframe(report_df, use_container_width=True)
    
    csv = report_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Final Audit Report", csv, "Jigawa_Audit_Final.csv", "text/csv")
