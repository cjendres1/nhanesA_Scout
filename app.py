import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Import localconverter from rpy2
from rpy2.robjects.conversion import localconverter

# -------------------------------------------------------------
# 1. Initialize the R Bridge and Install nhanesA if missing
# -------------------------------------------------------------
@st.cache_resource
def init_r_bridge():
    """Installs nhanesA in the container and imports rpy2 modules."""
    import rpy2.robjects as robjects
    from rpy2.robjects.packages import importr, isinstalled
    
    # Check if nhanesA is installed; if not, install it
    if not isinstalled('nhanesA'):
        utils = importr('utils')
        utils.chooseCRANmirror(ind=1) # Select first cloud mirror
        utils.install_packages('nhanesA')
        
    return importr('nhanesA')

# Load your package safely
try:
    nhanes = init_r_bridge()
except Exception as e:
    st.error(f"Failed to load R bridge: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. Data Fetching (Using Modern Local Conversion)
# -------------------------------------------------------------
@st.cache_data
def fetch_nhanes_table(table_name):
    """Calls nhanesA R function and returns a clean Pandas DataFrame."""
    import rpy2.robjects as robjects
    from rpy2.robjects import pandas2ri
    
    # 1. Get the raw R object using your package
    r_data = nhanes.nhanes(table_name)
    
    # 2. Convert R dataframe to Pandas using a local converter context
    # This replaces pandas2ri.activate() and avoids deprecation issues!
    with localconverter(robjects.default_converter + pandas2ri.converter) as cv:
        pd_df = robjects.conversion.get_conversion().rpy2py(r_data)
        
    return pd_df