import streamlit as st
import pandas as pd
import os

# Set up clean, wide layout
st.set_page_config(
    page_title="NHANES Scout",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔎 NHANES Scout")
st.caption("A lightning-fast, offline-first explorer for NHANES Demographics metadata.")

# -------------------------------------------------------------
# 1. High-Performance Data Loaders (With Column Auto-Mapping)
# -------------------------------------------------------------
@st.cache_data
def load_manifests():
    """Loads cached NHANES metadata files from the repository."""
    demo_path = "cache_demo_manifest.csv"
    vars_path = "cache_variables_manifest.csv"
    
    # Fallback to look in the current directory if they are named without extensions
    if not os.path.exists(demo_path) and os.path.exists("cache_demo_manifest"):
        demo_path = "cache_demo_manifest"
    if not os.path.exists(vars_path) and os.path.exists("cache_variables_manifest"):
        vars_path = "cache_variables_manifest"

    try:
        df_demo = pd.read_csv(demo_path)
        df_vars = pd.read_csv(vars_path)
        
        # --- Clean up and Standardize df_demo Columns ---
        # Make all column names uppercase to strip away any casing issues
        df_demo.columns = [col.upper() for col in df_demo.columns]
        
        # Ensure 'TABLE' is the standardized column name
        # If 'TABLE' is missing but something like 'SOURCETABLE' exists, rename it
        if 'TABLE' not in df_demo.columns:
            possible_cols = [c for c in df_demo.columns if 'TABLE' in c]
            if possible_cols:
                df_demo.rename(columns={possible_cols[0]: 'TABLE'}, inplace=True)

        # --- Clean up and Standardize df_vars Columns ---
        df_vars.columns = [col.upper() for col in df_vars.columns]
        
        if 'TABLE' not in df_vars.columns:
            # Check for alternative names like 'SOURCETABLE' or 'TABLENAME'
            alt_cols = [c for c in df_vars.columns if 'TABLE' in c or 'TAB' in c]
            if alt_cols:
                df_vars.rename(columns={alt_cols[0]: 'TABLE'}, inplace=True)
            else:
                # If all else fails, log columns for debugging
                st.error(f"Could not find a table identifier column in variables. Available columns: {list(df_vars.columns)}")
                
        return df_demo, df_vars
        
    except Exception as e:
        st.error(f"Error loading cache files: {e}")
        return None, None

# Load datasets
df_demo, df_vars = load_manifests()

if df_demo is None or df_vars is None:
    st.warning("⚠️ Cache files not detected. Please ensure 'cache_demo_manifest.csv' and 'cache_variables_manifest.csv' are pushed to your GitHub repository root.")
    st.stop()

# -------------------------------------------------------------
# 2. Sidebar Navigation & Global Stats
# -------------------------------------------------------------
with st.sidebar:
    st.header("📊 Database Stats")
    st.metric("Total Demographics Tables", f"{df_demo['Table'].nunique()}")
    st.metric("Total Indexed Variables", f"{len(df_vars):,}")
    
    st.write("---")
    st.markdown(
        """
        **About NHANES Scout**
        This tool provides instantaneous exploration of NHANES demographic tables. 
        Because it runs entirely on local pre-cached metadata, it remains 100% operational even when the CDC servers are down.
        """
    )

# -------------------------------------------------------------
# 3. Main Dashboard UI
# -------------------------------------------------------------
tab1, tab2 = st.tabs(["📂 Tables Directory", "🔑 Variable Explorer"])

# --- TAB 1: TABLES DIRECTORY ---
with tab1:
    st.subheader("Demographics Tables Manifest")
    st.write("Browse all historical demographic cycles found in the `nhanesA` metadata:")
    
    # Clean up column displays if needed and show interactive table
    st.dataframe(
        df_demo, 
        use_container_width=True,
        column_config={
            "Table": "Table Code",
            "TableDesc": "Description",
            "BeginYear": "Start Year",
            "EndYear": "End Year"
        }
    )

# --- TAB 2: VARIABLE EXPLORER ---
with tab2:
    st.subheader("Variable Inspector")
    
    # Create dropdown to choose which table to inspect
    available_tables = sorted(df_demo['TABLE'].unique())
    selected_table = st.selectbox(
        "Select an NHANES Demographic Table to inspect its variables:",
        options=available_tables,
        index=len(available_tables) - 1  # Default to the most recent cycle
    )
    
    # Filter variables on the fly (using our standardized upper-case column names)
    filtered_vars = df_vars[df_vars['TABLE'] == selected_table].copy()
    
    st.write(f"Showing variables present in **`{selected_table}`**:")
    
    # Display the variable details
    if not filtered_vars.empty:
        st.metric("Variables in this Table", len(filtered_vars))
        
        # Match whatever casing VarName / VarDesc ended up with
        var_col = 'VARNAME' if 'VARNAME' in filtered_vars.columns else ('VARIABLE' if 'VARIABLE' in filtered_vars.columns else filtered_vars.columns[0])
        desc_col = 'VARDESC' if 'VARDESC' in filtered_vars.columns else ('DESCRIPTION' if 'DESCRIPTION' in filtered_vars.columns else filtered_vars.columns[1])
        
        # Selectable/searchable data grid of the variables
        st.dataframe(
            filtered_vars, 
            use_container_width=True,
            column_config={
                var_col: "Variable Name",
                desc_col: "Detailed Label/Description"
            }
        )
    else:
        st.info(f"No variables found matching table code `{selected_table}` in cache.")
        