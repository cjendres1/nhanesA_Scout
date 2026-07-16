import streamlit as st
import pandas as pd
import numpy as np
import os
import pickle
from scipy.sparse import load_npz

# Page setup
st.set_page_config(page_title="NHANES Scout", page_icon="🔎", layout="wide")
st.title("🔎 NHANES Scout")
st.caption("Locate any NHANES tables based on search terms, bundle demographics, and generate Python loading code.")

# -------------------------------------------------------------
# 1. High-Performance Caching Loaders
# -------------------------------------------------------------
@st.cache_resource
def load_semantic_model():
    """Loads the pre-fitted Scikit-Learn vectorizer model."""
    pkl_path = "cache_vectorizer.pkl"
    if os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    return None

@st.cache_data
def load_global_manifests(demo_mtime, vars_mtime):
    demo_path = "cache_demo_manifest.csv"
    vars_path = "cache_variables_manifest.csv"
    
    if not os.path.exists(demo_path) or not os.path.exists(vars_path):
        return None, None
        
    df_tables = pd.read_csv(demo_path)
    df_vars = pd.read_csv(vars_path)
    
    # Standardize column naming to upper-case
    df_tables.columns = [col.upper() for col in df_tables.columns]
    df_vars.columns = [col.upper() for col in df_vars.columns]
    
    return df_tables, df_vars

@st.cache_data
def load_vector_embeddings(emb_mtime):
    emb_path = "cache_vector_embeddings.npz"
    if os.path.exists(emb_path):
        return load_npz(emb_path)
    return None

# Manage file modification times for auto-cache busting
demo_mtime = os.path.getmtime("cache_demo_manifest.csv") if os.path.exists("cache_demo_manifest.csv") else 0
vars_mtime = os.path.getmtime("cache_variables_manifest.csv") if os.path.exists("cache_variables_manifest.csv") else 0
emb_mtime = os.path.getmtime("cache_vector_embeddings.npz") if os.path.exists("cache_vector_embeddings.npz") else 0

# Load datasets and vector indexes
df_tables, df_vars = load_global_manifests(demo_mtime, vars_mtime)
embeddings = load_vector_embeddings(emb_mtime)
vectorizer_model = load_semantic_model()

# Verify that resources were successfully loaded
if df_tables is None or df_vars is None:
    st.error("⚠️ Local data cache files ('cache_demo_manifest.csv' and 'cache_variables_manifest.csv') not detected.")
    st.stop()

if embeddings is None or vectorizer_model is None:
    st.error("⚠️ Semantic search files ('cache_vector_embeddings.npz' and 'cache_vectorizer.pkl') not detected.")
    st.stop()

# Build a fast-lookup set of RDC (Research Data Center) restricted tables
rdc_tables = set()
for df in [df_tables, df_vars]:
    # Look for any constraint column
    constraint_col = [col for col in df.columns if 'CONSTRAINT' in col]
    if constraint_col:
        col_name = constraint_col[0]
        # Identify tables flagged with restrictions
        restricted = df[df[col_name].astype(str).str.lower().str.contains('rdc|limited|restrict|secure', na=False)]
        if 'TABLE' in restricted.columns:
            rdc_tables.update(restricted['TABLE'].unique())

# -------------------------------------------------------------
# 2. Search Inputs & Configurations (With Sidebar Controls)
# -------------------------------------------------------------
st.sidebar.header("⚙️ Search Controls")

search_type = st.sidebar.selectbox(
    "Search Type:",
    options=["Semantic Search (AI Concept Matching)", "Literal Search (Exact Keywords)"],
    help="Semantic Search leverages the mathematical vector relationships to find similar concepts, even if spelled differently."
)

# Configurable minimum similarity threshold
similarity_threshold = st.sidebar.slider(
    "Min Similarity Score",
    min_value=0.2,
    max_value=0.8,
    value=0.30,
    step=0.05,
    disabled=(search_type == "Literal Search (Exact Keywords)"),
    help="Adjust how strictly the semantic search engine matches concepts. Higher scores yield fewer, more precise matches."
)

st.write("### 🔎 Step 1: Search Variable Metadata")
search_input = st.text_input(
    "Enter keywords or search concepts (comma-separated for multi-term queries):",
    placeholder="e.g., blood pressure, mercury, diabetes, age",
    help="Use commas to search for multiple concepts at once."
)

# Establish matching dataframe container
matched_vars = pd.DataFrame()

# -------------------------------------------------------------
# 3. Search & Filter Engine (Smart Phrasing & Comma Separation)
# -------------------------------------------------------------
if search_input.strip():
    # Dynamic column identification to prevent errors if names differ
    var_col = 'VARNAME' if 'VARNAME' in df_vars.columns else ('VARIABLE' if 'VARIABLE' in df_vars.columns else df_vars.columns[0])
    desc_col = 'VARDESC' if 'VARDESC' in df_vars.columns else ('DESCRIPTION' if 'DESCRIPTION' in df_vars.columns else df_vars.columns[1])
    
    # Clean up and split the user's input by commas
    raw_concepts = search_input.split(",")
    search_concepts = [concept.strip().replace('"', '').replace("'", "") for concept in raw_concepts if concept.strip()]
    
    matched_vars_by_concept = []
    
    # --- METHOD A: SEMANTIC MATCHING (SPARSE TF-IDF) ---
    if search_type == "Semantic Search (AI Concept Matching)":
        with st.spinner("Analyzing semantics..."):
            for concept in search_concepts:
                # Convert user query to sparse representation
                query_vector = vectorizer_model.transform([concept])
                
                # High-speed cosine similarity on sparse structures
                from sklearn.preprocessing import normalize
                normalized_embeddings = normalize(embeddings, norm='l2', axis=1)
                normalized_query = normalize(query_vector, norm='l2', axis=1)
                
                # Dot product of sparse matrices is incredibly fast
                similarities = (normalized_embeddings * normalized_query.T).toarray().squeeze()
                
                # Filter variables that hit the user's chosen threshold
                matching_indices = np.where(similarities >= similarity_threshold)[0]
                
                if len(matching_indices) > 0:
                    concept_df = df_vars.iloc[matching_indices].copy()
                    concept_df['SIMILARITY'] = similarities[matching_indices]
                    concept_df['MATCHED_CONCEPT'] = concept
                    matched_vars_by_concept.append(concept_df)
                    
        if matched_vars_by_concept:
            # Drop duplicates if a variable matched multiple semantic targets
            matched_vars = pd.concat(matched_vars_by_concept).drop_duplicates(subset=['TABLE', var_col])
        else:
            matched_vars = pd.DataFrame()

    # --- METHOD B: LITERAL SEARCH (PREVIOUS EXACT KEYWORD CODE) ---
    else:
        if len(search_concepts) > 1:
            st.write(f"Parsed **{len(search_concepts)}** search concepts: " + ", ".join([f"`{c}`" for c in search_concepts]))
            search_mode = st.radio(
                "Combination Mode:",
                options=["Match ALL concepts (AND)", "Match ANY concept (OR)"],
                horizontal=True
            )
        else:
            search_mode = "Match ANY concept (OR)"

        for concept in search_concepts:
            words_in_concept = concept.lower().split()
            concept_df = df_vars.copy()
            for word in words_in_concept:
                concept_df = concept_df[
                    concept_df[var_col].str.lower().str.contains(word, na=False) |
                    concept_df[desc_col].str.lower().str.contains(word, na=False)
                ]
            concept_df = concept_df.copy()
            concept_df['MATCHED_CONCEPT'] = concept
            matched_vars_by_concept.append(concept_df)

        if search_mode == "Match ALL concepts (AND)":
            tables_per_concept = [set(cdf['TABLE'].unique()) for cdf in matched_vars_by_concept]
            common_tables = set.intersection(*tables_per_concept) if tables_per_concept else set()
            all_matches_combined = pd.concat(matched_vars_by_concept)
            matched_vars = all_matches_combined[all_matches_combined['TABLE'].isin(common_tables)].copy()
        else:
            matched_vars = pd.concat(matched_vars_by_concept).drop_duplicates(subset=['TABLE', var_col])

# -------------------------------------------------------------
# 4. Result Display & Selection UI
# -------------------------------------------------------------
selected_tables = []
if not matched_vars.empty:
    # Tag rows if their corresponding table is restricted
    matched_vars['RDC_ONLY'] = matched_vars['TABLE'].isin(rdc_tables)
    
    # Report performance stats
    distinct_tables_count = matched_vars['TABLE'].nunique()
    rdc_match_count = matched_vars[matched_vars['RDC_ONLY'] == True]['TABLE'].nunique()
    
    st.success(
        f"Found **{len(matched_vars)}** matching variables across **{distinct_tables_count}** distinct tables!"
    )
    
    # Inform users about visual cues
    if rdc_match_count > 0:
        st.info(
            f"⚠️ **Note:** {rdc_match_count} table(s) require Research Data Center (RDC) access and are highlighted in **red**. "
            "These restricted tables cannot be downloaded or included in the auto-generated code snippet."
        )

    # Sort results to place best semantic hits at the top
    if 'SIMILARITY' in matched_vars.columns:
        matched_vars = matched_vars.sort_values(by='SIMILARITY', ascending=False)
    
    # Filter selection checklist to only show non-RDC downloadable tables
    unique_tables = sorted(matched_vars['TABLE'].unique())
    downloadable_tables = [t for t in unique_tables if t not in rdc_tables]
    
    selected_tables = st.multiselect(
        "Choose NHANES tables to bundle into download package:",
        options=downloadable_tables,
        default=downloadable_tables[:5] if len(downloadable_tables) > 0 else []
    )
    
    # Apply soft-red conditional styling to the dataframe row if it is RDC_ONLY
    def style_rdc_rows(row):
        color = 'background-color: #ffebee' if row['RDC_ONLY'] else ''
        return [color] * len(row)
    
    styled_df = matched_vars.style.apply(style_rdc_rows, axis=1)
    
    # Display styled dataframe, hiding the control columns (USECONSTRAINTS & RDC_ONLY)
    hide_cols = {
        "RDC_ONLY": None,
        "USECONSTRAINTS": None,
        "CONSTRAINTS": None
    }
    
    st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True,
        column_config=hide_cols
    )
else:
    if search_input.strip():
        st.warning("No variables matched your search parameters.")

# -------------------------------------------------------------
# 5. Demographics Bundling & Python Code Generation
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
