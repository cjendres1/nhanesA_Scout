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
    # Use localconverter() for rpy2 v3.5.1 compatibility
    with localconverter(custom_converter) as cv:
        nhanes = init_r_bridge()
    st.success("🎉 R-to-Python Bridge Connected Successfully!")
except Exception as e:
    st.error(f"❌ Failed to load R bridge: {e}")
    st.stop()

# -------------------------------------------------------------
# 2. Interactive Test (Query Table Metadata with CDC Fallback)
# -------------------------------------------------------------
st.write("### Test Connection")
st.info("💡 Note: NHANES metadata is fetched live from the CDC. If the CDC servers are down or slow, the app will load fallback mock data.")

if st.button("Query NHANES table metadata"):
    with st.spinner("Attempting to connect to CDC via R `nhanesA`..."):
        success = False
        pd_df = None
        
        try:
            # We use localconverter(custom_converter) for safe translations
            with localconverter(custom_converter) as cv:
                # Set an R-level option to prevent infinite waiting if possible
                # Fetch R data
                r_data = nhanes.nhanesManifest("DEMO")
                # Convert the resulting R dataframe to Pandas
                pd_df = robjects.conversion.get_conversion().rpy2py(r_data)
                success = True
                st.success("🎉 Successfully retrieved live data from CDC servers!")
                
        except Exception as e:
            st.warning(f"⚠️ CDC servers are currently unreachable or slow. Loading offline fallback data...")
            # Create a mock demographics table so you can keep testing your app's UI
            pd_df = pd.DataFrame({
                'Table': ['DEMO_A', 'DEMO_B', 'DEMO_C', 'DEMO_D', 'DEMO_E', 'DEMO_F', 'DEMO_G', 'DEMO_H'],
                'TableDesc': [
                    'Demographic Variables (1999-2000)',
                    'Demographic Variables (2001-2002)',
                    'Demographic Variables (2003-2004)',
                    'Demographic Variables (2005-2006)',
                    'Demographic Variables (2007-2008)',
                    'Demographic Variables (2009-2010)',
                    'Demographic Variables (2011-2012)',
                    'Demographic Variables (2013-2014)'
                ],
                'BeginYear': [1999, 2001, 2003, 2005, 2007, 2009, 2011, 2013],
                'EndYear': [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014]
            })

        # Display the resulting dataframe (either live or fallback)
        if pd_df is not None:
            st.write("### Demographic Tables Manifest")
            st.dataframe(pd_df, use_container_width=True)