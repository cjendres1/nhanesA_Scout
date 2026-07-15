import streamlit as st
import pandas as pd
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri

# Set up page layout
st.set_page_config(page_title="NHANES Scout", layout="wide")
st.title("🔎 NHANES Scout")
st.caption("Powered by R package nhanesA & Python Streamlit")

# -------------------------------------------------------------
# 1. Thread-Safe R Bridge Initializer (rpy2 <= 3.5.1)
# -------------------------------------------------------------
@st.cache_resource
def init_r_bridge():
    from rpy2.robjects.packages import importr, isinstalled
    
    # Activate automatic R-to-Pandas dataframe conversion
    pandas2ri.activate()
    
    # Install nhanesA silently if it's missing
    if not isinstalled('nhanesA'):
        utils = importr('utils')
        utils.install_packages(
            'nhanesA', 
            repos='https://cloud.r-project.org', 
            dependencies=True
        )
    return importr('nhanesA')

# Safe initialization
try:
    nhanes = init_r_bridge()
    st.success("🎉 R-to-Python Bridge Connected Successfully!")
except Exception as e:
    st.error(f"❌ Failed to load R bridge: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. Interactive Test (Query Table Metadata)
# -------------------------------------------------------------
st.write("### Test Connection")
if st.button("Query NHANES table metadata"):
    with st.spinner("Calling R `nhanesA::nhanesManifest`..."):
        try:
            # Query a simple metadata table
            r_data = nhanes.nhanesManifest("DEMO")
            
            # Convert the R dataframe to Pandas
            pd_df = pandas2ri.rpy2py(r_data)
            
            st.write("Returned Tables:")
            st.dataframe(pd_df.head(10))
        except Exception as e:
            st.error(f"Error querying table metadata: {e}")