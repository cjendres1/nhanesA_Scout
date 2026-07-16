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
    """Installs nhanesA safely into a user-writable directory on Streamlit Cloud."""
    from rpy2.robjects.packages import importr, isinstalled
    import rpy2.robjects as robjects
    import os

    # 1. Define a local, writable directory in the user's home folder for R packages
    user_home = os.path.expanduser("~")
    r_libs_path = os.path.join(user_home, "R", "library")
    
    # Create the directory if it doesn't exist
    if not os.path.exists(r_libs_path):
        os.makedirs(r_libs_path)
        
    # Tell the local environment to look at this directory for R packages
    os.environ["R_LIBS_USER"] = r_libs_path
    
    # 2. Check if nhanesA is already installed in our custom directory
    # We pass our local path to 'lib_loc' so isinstalled searches there
    if not isinstalled('nhanesA', lib_loc=r_libs_path):
        utils = importr('utils')
        
        # Force R to install directly to our user-writable library path
        utils.install_packages(
            'nhanesA', 
            lib=r_libs_path,            # Crucial: Forces install to writable home directory
            repos='https://cloud.r-project.org', 
            dependencies=True
        )
        
    # 3. Load the package, specifying where it lives
    return importr('nhanesA', lib_loc=r_libs_path)

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