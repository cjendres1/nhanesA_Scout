import streamlit as st
import pandas as pd
import plotly.express as px

# 1. Import necessary rpy2 conversion modules
import rpy2.robjects as robjects
from rpy2.robjects import pandas2ri
from rpy2.robjects.conversion import localconverter

# Create a combined converter for R default and Pandas
# We define it globally, but we will call its context manager locally
custom_converter = robjects.default_converter + pandas2ri.converter

# -------------------------------------------------------------
# 1. Initialize the R Bridge and Install nhanesA if missing
# -------------------------------------------------------------
@st.cache_resource
def init_r_bridge():
    """Installs nhanesA in the container and imports rpy2 modules."""
    from rpy2.robjects.packages import importr, isinstalled
    
    # Check if nhanesA is installed; if not, install it
    if not isinstalled('nhanesA'):
        utils = importr('utils')
        utils.chooseCRANmirror(ind=1) # Select first cloud mirror
        utils.install_packages('nhanesA')
        
    return importr('nhanesA')

# Load your package inside the default converter context
try:
    with custom_converter.context(): # Force context variables into Streamlit's thread
        nhanes = init_r_bridge()
except Exception as e:
    st.error(f"Failed to load R bridge: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. Data Fetching (Using Thread-Safe Context Manager)
# -------------------------------------------------------------
@st.cache_data
def fetch_nhanes_table(table_name):
    """Calls nhanesA R function and returns a clean Pandas DataFrame."""
    
    # Wrapping everything in the custom_converter context ensures that 
    # Streamlit's threads always know how to translate R objects to Pandas.
    with custom_converter.context():
        # 1. Get the raw R object using your package
        r_data = nhanes.nhanes(table_name)
        
        # 2. Convert R dataframe to Pandas DataFrame
        pd_df = robjects.conversion.get_conversion().rpy2py(r_data)
        
    return pd_df