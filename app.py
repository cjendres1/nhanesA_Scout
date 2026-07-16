import streamlit as st
import pandas as pd
import os

# Page setup
st.set_page_config(page_title="NHANES Scout", page_icon="🔎", layout="wide")
st.title("🔎 NHANES Scout")
st.caption("Locate any NHANES tables based on search terms, bundle demographics, and generate Python loading code.")

# -------------------------------------------------------------
# 1. High-Performance Caching Loaders
# -------------------------------------------------------------
@st.cache_data
def load_global_manifests():
    demo_path = "cache_demo_manifest.csv"
    vars_path = "cache_variables_manifest.csv"
    
    if not os.path.exists(demo_path) or not os.path.exists(vars_path):
        return None, None
        
    df_tables = pd.read_csv(demo_path)
    df_vars = pd.read_csv(vars_path)
    
    # Force uppercase column safety
    df_tables.columns = [col.upper() for col in df_tables.columns]
    df_vars.columns = [col.upper() for col in df_vars.columns]
    
    return df_tables, df_vars

df_tables, df_vars = load_global_manifests()

if df_tables is None or df_vars is None:
    st.warning("⚠️ High-capacity cache files not detected. Ensure 'cache_demo_manifest.csv' and 'cache_variables_manifest.csv' are uploaded.")
    st.stop()

# -------------------------------------------------------------
# 2. Search & Filter Engine (Deduplicated with Match Counts)
# -------------------------------------------------------------
st.write("### 🔍 Step 1: Search the NHANES Universe")
search_term = st.text_input(
    "Enter keywords (e.g., 'cholesterol', 'blood pressure', 'income', 'diet')", 
    value="",
    help="Searches across all NHANES variable names and descriptions."
)

if search_term.strip():
    term = search_term.lower()
    
    # 1. Search the master variables dataframe
    matched_vars = df_vars[
        df_vars['VARNAME'].str.lower().str.contains(term, na=False) |
        df_vars['VARDESC'].str.lower().str.contains(term, na=False)
    ].copy()
    
    if not matched_vars.empty:
        # 2. Group by table and count the number of matching variables in each table
        match_counts = matched_vars.groupby('TABLE').size().reset_index(name='MATCH_COUNT')
        
        # 3. Pull table metadata, ensuring we have strictly 1 row per table code
        unique_tables_catalog = df_tables.drop_duplicates(subset=['TABLE']).copy()
        
        # 4. Merge the match counts with our unique tables catalog
        matched_tables_df = unique_tables_catalog.merge(match_counts, on='TABLE', how='inner')
        
        # 5. Sort by the number of matches descending (highest relevance first)
        matched_tables_df = matched_tables_df.sort_values(by='MATCH_COUNT', ascending=False)
        
        st.success(f"Found **{len(matched_tables_df)}** unique tables matching your search term '{search_term}'.")
        
        # Display matching tables with interactive checkbox selection
        st.write("#### Select tables to retrieve:")
        
        # Insert selection column
        matched_tables_df.insert(0, "Select", True)  # Default all matches to selected
        
        edited_df = st.data_editor(
            matched_tables_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True),
                "TABLE": "Table Code",
                "MATCH_COUNT": st.column_config.NumberColumn(
                    "Matched Variables",
                    help="The number of unique variables in this table matching your search term.",
                    format="%d ⭐"
                ),
                "TABLEDESC": "Description / Title",
                "BEGINYEAR": "Start Year",
                "ENDYEAR": "End Year",
                "COMPONENT": "Component"
            }
        )
        
        # Extract the finalized selection list from the editor
        selected_tables = edited_df[edited_df["Select"] == True]["TABLE"].tolist()
        
    else:
        st.warning("No tables found matching those criteria. Try another keyword.")
        selected_tables = []
else:
    st.info("Please enter a search term above to begin discovering tables.")
    selected_tables = []

# -------------------------------------------------------------
# 3. Demographics Bundling & Python Code Generation
# -------------------------------------------------------------
if selected_tables:
    st.write("---")
    st.write("### 📦 Step 2: Configure Bundle & Retrieve")
    
    # Option: Include demographics table automatically
    include_demos = st.checkbox(
        "💡 **Auto-include corresponding Demographics tables**", 
        value=True,
        help="Recommended. This auto-resolves the demographics table for each selected table's cycle so you can merge them on 'SEQN' later."
    )
    
    # Build final list of tables to download
    final_download_list = list(selected_tables)
    
    if include_demos:
        demo_additions = []
        # Find which years/cycles the selected tables belong to
        for table in selected_tables:
            # Match the row in the table catalog to find the cycle year
            row = df_tables[df_tables['TABLE'] == table]
            if not row.empty:
                begin_year = int(row.iloc[0]['BEGINYEAR'])
                # Map starting year to standard NHANES demographics table naming
                # 1999 -> DEMO, 2001 -> DEMO_B, 2003 -> DEMO_C, etc.
                if begin_year == 1999:
                    demo_table = "DEMO"
                else:
                    cycle_letter = chr(65 + int((begin_year - 1999) / 2)) # Converts years to _B, _C, etc.
                    demo_table = f"DEMO_{cycle_letter}"
                
                if demo_table not in final_download_list and demo_table not in demo_additions:
                    demo_additions.append(demo_table)
        
        final_download_list.extend(demo_additions)
        if demo_additions:
            st.info(f"Adding demographic baselines: `{', '.join(demo_additions)}`")

    # Display final queue
    st.write("**Your Final Data Package List:**")
    st.code(", ".join(final_download_list))
    
    # Generate the Easy Python Retrieval Code
    st.write("#### 🐍 Step 3: Copy Code to Python")
    st.write("Because the CDC servers limit Streamlit web-scraping speed, use this optimized snippet to load these files directly into your local Python environment:")
    
    # Generate copy-pasteable script utilizing pd.read_sas or a wrapper
    python_snippet = f"""import pandas as pd

# List of NHANES tables identified via NHANES Scout
tables_to_load = {final_download_list}

def fetch_nhanes_tables(table_list):
    datasets = {{}}
    for table in table_list:
        print(f"Downloading table: {{table}}...")
        # NHANES tables are hosted as SAS Transport (.XPT) files on the CDC website
        url = f"https://wwwn.cdc.gov/Nchs/Nhanes/{{table[:4]}}/{{table}}.XPT"
        try:
            datasets[table] = pd.read_sas(url)
            print(f" -> Loaded {{len(datasets[table])}} rows.")
        except Exception as e:
            # Fallback if table name format is slightly different on CDC
            try:
                # Some tables reside in the root demographics directory
                url_alt = f"https://wwwn.cdc.gov/Nchs/Nhanes/Demographics/{{table}}.XPT"
                datasets[table] = pd.read_sas(url_alt)
                print(f" -> Loaded {{len(datasets[table])}} rows (alternative path).")
            except Exception as alt_err:
                print(f" ❌ Error fetching {{table}}: {{alt_err}}")
    return datasets

# Fetch all selected tables instantly
nhanes_data = fetch_nhanes_tables(tables_to_load)

# Example: Inspecting one of the loaded DataFrames
# first_table = list(nhanes_data.keys())[0]
# print(nhanes_data[first_table].head())
"""
    
    st.code(python_snippet, language="python")
