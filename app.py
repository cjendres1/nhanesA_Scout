import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------------------------------------------
# 1. Initialize the R Bridge and Install nhanesA if missing
# -------------------------------------------------------------
@st.cache_resource
def init_r_bridge():
    """Installs nhanesA in the container and imports rpy2 modules."""
    import rpy2.robjects as robjects
    from rpy2.robjects.packages import importr, isinstalled
    from rpy2.robjects import pandas2ri
    
    # Activate automatic conversion between R data frames and Pandas DataFrames
    pandas2ri.activate()
    
    # Check if nhanesA is installed; if not, install it
    if not isinstalled('nhanesA'):
        utils = importr('utils')
        utils.chooseCRANmirror(ind=1) # Select first cloud mirror
        utils.install_packages('nhanesA')
        
    return importr('nhanesA')

# Load your package (cached so it only loads once)
try:
    nhanes = init_r_bridge()
except Exception as e:
    st.error(f"Failed to load R bridge: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. UI Layout
# -------------------------------------------------------------
st.title("🔎 NHANES Scout")
st.caption("Powered by the R package `nhanesA` & Python Streamlit")

# Sidebar for manual navigation
st.sidebar.header("Data Selector")
cycle = st.sidebar.selectbox(
    "Survey Cycle", 
    ["2017-2018", "2015-2016", "2013-2014", "2011-2012"],
    index=0
)

# Convert common year strings to nhanesA shorthand (e.g., '2017-2018' -> 'J')
cycle_map = {"2017-2018": "J", "2015-2016": "I", "2013-2014": "H", "2011-2012": "G"}
cycle_code = cycle_map[cycle]

category = st.sidebar.selectbox(
    "Category", 
    ["DEMOGRAPHICS", "EXAMINATION", "LABORATORY", "QUESTIONNAIRE"]
)

# -------------------------------------------------------------
# 3. Data Fetching (Wrapped in Streamlit Cache)
# -------------------------------------------------------------
@st.cache_data
def fetch_nhanes_table(table_name):
    """Calls nhanesA R function and returns a clean Pandas DataFrame."""
    # This calls nhanesTranslate(nhanesA::nhanes('TABLE')) under the hood
    r_data = nhanes.nhanes(table_name)
    # Convert R dataframe to Pandas
    from rpy2.robjects import conversion, default_converter
    pd_df = conversion.localconverter(default_converter).rpy2py(r_data)
    return pd_df

# Let user type a table name manually for now (e.g., "DEMO_J" or "BMX_J")
table_input = st.text_input("Enter NHANES Table Code (e.g., DEMO_J, BMX_J):", value=f"DEMO_{cycle_code}")

if table_input:
    with st.spinner(f"Fetching {table_input} via nhanesA..."):
        try:
            df = fetch_nhanes_table(table_input)
            
            # Display basic data overview
            st.success(f"Successfully loaded {table_input}! ({df.shape[0]} rows, {df.shape[1]} columns)")
            
            st.subheader("Data Preview")
            st.dataframe(df.head(100)) # Show first 100 rows to keep UI snappy
            
            # Let them download the raw data
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Full CSV",
                data=csv,
                file_name=f"{table_input}.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Could not fetch table. Ensure the code '{table_input}' is correct for cycle {cycle}.")