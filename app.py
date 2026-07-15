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
    """Installs nhanesA safely and silently in a non-interactive container."""
    from rpy2.robjects.packages import importr, isinstalled
    import rpy2.robjects as robjects

    if not isinstalled('nhanesA'):
        # 1. Import R's core 'utils' package
        utils = importr('utils')
        
        # 2. Force install nhanesA non-interactively
        # - repos: Hardcodes the cloud mirror to bypass the interactive prompt
        # - dependencies=True: Ensures it pulls in any missing helper packages
        # - INSTALL_opts="--no-multiarch": Speeds up installation on Linux
        utils.install_packages(
            'nhanesA', 
            repos='https://cloud.r-project.org', 
            dependencies=True
        )
        
    return importr('nhanesA')

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