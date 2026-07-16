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
# 2. Search & Filter Engine (Smart Phrasing & Comma Separation)
# -------------------------------------------------------------
st.write("### 🔍 Step 1: Search the NHANES Universe")

# Clarified and intuitive instructions for users
search_input = st.text_input(
    "Enter search terms (separate distinct topics with commas):", 
    placeholder="e.g., blood pressure, diet",
    help="Use a comma to search multiple topics at once (e.g., 'blood pressure, income'). Spaces inside a phrase will be treated as a single concept."
)

if search_input.strip():
    # 1. Split search input by COMMAS to parse distinct concepts, stripping spaces and quotes
    raw_concepts = search_input.split(",")
    search_concepts = [concept.strip().replace('"', '').replace("'", "") for concept in raw_concepts if concept.strip()]
    
    # Locate the correct column names dynamically
    var_col = 'VARNAME' if 'VARNAME' in df_vars.columns else ('VARIABLE' if 'VARIABLE' in df_vars.columns else df_vars.columns[0])
    desc_col = 'VARDESC' if 'VARDESC' in df_vars.columns else ('DESCRIPTION' if 'DESCRIPTION' in df_vars.columns else df_vars.columns[1])
    
    # 2. If the user provided multiple comma-separated terms, let them choose the logical join
    if len(search_concepts) > 1:
        st.write(f"Parsed **{len(search_concepts)}** separate search concepts: " + ", ".join([f"`{c}`" for c in search_concepts]))
        search_mode = st.radio(
            "Search Combination Mode:",
            options=["Match ALL concepts (AND)", "Match ANY concept (OR)"],
            horizontal=True,
            help=(
                "Match ALL: A table must contain matches for EVERY comma-separated concept (e.g., must contain a blood pressure variable AND a diet variable).\n"
                "Match ANY: Returns tables containing any of the concepts, combined and deduplicated."
            )
        )
    else:
        # Default to a single-concept search if no commas are used
        search_mode = "Match ANY concept (OR)"

    # 3. Apply the filtering logic across concepts
    matched_vars_by_concept = []
    
    for concept in search_concepts:
        # A single concept might contain spaces (e.g., "blood pressure"). We look for rows that contain ALL words in that concept.
        words_in_concept = concept.lower().split()
        concept_df = df_vars.copy()
        for word in words_in_concept:
            concept_df = concept_df[
                concept_df[var_col].str.lower().str.contains(word, na=False) |
                concept_df[desc_col].str.lower().str.contains(word, na=False)
            ]
        # Keep track of which variables matched this specific comma-separated concept
        concept_df = concept_df.copy()
        concept_df['MATCHED_CONCEPT'] = concept
        matched_vars_by_concept.append(concept_df)

    # 4. Combine the filtered subsets depending on AND / OR logic
    if search_mode == "Match ALL concepts (AND)":
        # Get tables that have matches across *every* individual concept list
        tables_per_concept = [set(cdf['TABLE'].unique()) for cdf in matched_vars_by_concept]
        common_tables = set.intersection(*tables_per_concept) if tables_per_concept else set()
        
        # Filter combined variable matches to only those in the common tables
        all_matches_combined = pd.concat(matched_vars_by_concept)
        matched_vars = all_matches_combined[all_matches_combined['TABLE'].isin(common_tables)].copy()
    else:
        # Match ANY: Combine and simply drop duplicates of matches (natively deduplicates tables)
        matched_vars = pd.concat(matched_vars_by_concept).drop_duplicates(subset=['TABLE', var_col])

    # 5. Process and display results if matches exist
    if not matched_vars.empty:
        # Count ONLY the UNIQUE variable names matching per table (deduplicated)
        match_counts = matched_vars.groupby('TABLE')[var_col].nunique().reset_index(name='MATCH_COUNT')
        
        # Get unique tables and merge with the strict unique match counts
        unique_tables_catalog = df_tables.drop_duplicates(subset=['TABLE']).copy()
        matched_tables_df = unique_tables_catalog.merge(match_counts, on='TABLE', how='inner')
        
        # Sort so tables with the most relevant search hits appear first
        matched_tables_df = matched_tables_df.sort_values(by='MATCH_COUNT', ascending=False)
        
        st.success(f"Found **{len(matched_tables_df)}** unique tables matching your criteria.")
        
        # --- Interactive Table Selection ---
        st.write("#### Select tables to retrieve:")
        
        # Ensure 'Select' checkbox column isn't already added
        if "Select" not in matched_tables_df.columns:
            matched_tables_df.insert(0, "Select", True)  # Default to selected
        
        edited_df = st.data_editor(
            matched_tables_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True),
                "TABLE": "Table Code",
                "MATCH_COUNT": st.column_config.NumberColumn(
                    "Matching Variables",
                    help="The exact number of unique variables in this table that matched your search query.",
                    format="%d ⭐"
                ),
                "TABLEDESC": "Description / Title",
                "BEGINYEAR": "Start Year",
                "ENDYEAR": "End Year",
                "COMPONENT": "Component"
            }
        )
        
        selected_tables = edited_df[edited_df["Select"] == True]["TABLE"].tolist()
        
        # --- View Exactly WHAT Matched ---
        st.write("---")
        with st.expander("👁️ View exactly which variables matched your search in each table"):
            for table_code in matched_tables_df['TABLE'].unique():
                table_specific_matches = matched_vars[matched_vars['TABLE'] == table_code].drop_duplicates(subset=[var_col])
                st.markdown(f"**`{table_code}`** ({len(table_specific_matches)} unique match(es)):")
                st.dataframe(
                    table_specific_matches[[var_col, desc_col, 'MATCHED_CONCEPT']], 
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "MATCHED_CONCEPT": "Search Category"
                    }
                )
                
    else:
        st.warning(f"No variables found matching your search. Try removing a concept or switching to 'Match ANY concept'.")
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
