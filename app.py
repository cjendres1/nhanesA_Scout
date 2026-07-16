import streamlit as st
import pandas as pd
import os

# Set up page layout
st.set_page_config(page_title="NHANES Scout", layout="wide")
st.title("🔎 NHANES Scout")
st.caption("Powered by R package nhanesA & Python Streamlit")

# -------------------------------------------------------------
# 1. Thread-Safe R Bridge Initializer
# -------------------------------------------------------------
@st.cache_resource
def init_r_bridge():
    """Installs nhanesA safely into a user-writable directory on Streamlit Cloud."""
    from rpy2.robjects.packages import importr, isinstalled
    import rpy2.robjects as robjects
    
    # 1. Define a local, writable directory in the user's home folder
    user_home = os.path.expanduser("~")
    r_libs_path = os.path.join(user_home, "R", "library")
    
    if not os.path.exists(r_libs_path):
        os.makedirs(r_libs_path)
        
    os.environ["R_LIBS_USER"] = r_libs_path
    
    # 2. Check if nhanesA is already installed in our custom directory
    if not isinstalled('nhanesA', lib_loc=r_libs_path):
        utils = importr('utils')
        utils.install_packages(
            'nhanesA', 
            lib=r_libs_path,
            repos='https://cloud.r-project.org', 
            dependencies=True
        )
        
    # 3. Load the package, specifying where it lives
    return importr('nhanesA', lib_loc=r_libs_path)

# Initialize global modules and import conversion rules
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
from rpy2.robjects.conversion import localconverter

# Build our combined converter
custom_converter = robjects.default_converter + pandas2ri.converter

# Load the bridge and assign it to the GLOBAL variable 'nhanes'
try:
    with custom_converter.context():
        # This assigns 'nhanes' globally so the button can see it
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
            # We use the thread-safe localconverter context to handle R-to-Python translations
            with custom_converter.context():
                # 1. Fetch R data using the globally defined 'nhanes' package
                r_data = nhanes.nhanesManifest("DEMO")
                
                # 2. Explicitly convert the resulting R dataframe to Pandas
                pd_df = robjects.conversion.get_conversion().rpy2py(r_data)
                
            st.write("Returned Tables:")
            st.dataframe(pd_df.head(10))
            
        except Exception as e:
            st.error(f"Error querying table metadata: {e}")
            