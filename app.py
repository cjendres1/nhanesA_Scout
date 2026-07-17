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
# Quick Guide (Tucked cleanly in a collapsible expander)
with st.expander("📖 Quick Start Guide", expanded=True):
    st.markdown("""
    **Complete these 3 steps to generate custom Python code to download your NHANES data:**
    
    1. 🔍 **Step 1: Enter Search Terms** – Type keywords (e.g., *blood pressure, mercury*) in the search box to scan NHANES variable metadata.
    2. 📋 **Step 2: Select NHANES Tables** – Use the multiselect box above the results table to choose which tables you want to bundle.
    3. 🐍 **Step 3: Generate Python Snippet** – Scroll down to copy the custom Python code to fetch and load your chosen tables instantly.
    """)

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
    constraint_col = [col for col in df.columns if 'CONSTRAINT' in col]
    if constraint_col:
        col_name = constraint_col[0]
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
    help="Semantic Search leverages vector relationships to find similar concepts, even if spelled differently."
)

# Configurable minimum similarity threshold
similarity_threshold = st.sidebar.slider(
    "Min Similarity Score",
    min_value=0.2,
    max_value=0.8,
    value=0.30,
    step=0.05,
    disabled=(search_type == "Literal Search (Exact Keywords)"),
    help="Adjust how strictly the semantic search engine matches concepts."
)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Restricted Data Settings")
# Persistent checkbox to control display of RDC-only tables (defaults to False)
show_rdc = st.sidebar.checkbox(
    "Display RDC-only tables", 
    value=False,
    help="Show restricted Research Data Center tables in search results."
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
    var_col = 'VARNAME' if 'VARNAME' in df_vars.columns else ('VARIABLE' if 'VARIABLE' in df_vars.columns else df_vars.columns[0])
    desc_col = 'VARDESC' if 'VARDESC' in df_vars.columns else ('DESCRIPTION' if 'DESCRIPTION' in df_vars.columns else df_vars.columns[1])
    
    raw_concepts = search_input.split(",")
    search_concepts = [concept.strip().replace('"', '').replace("'", "") for concept in raw_concepts if concept.strip()]
    
    matched_vars_by_concept = []
    
    # --- METHOD A: SEMANTIC MATCHING (SPARSE TF-IDF) ---
    if search_type == "Semantic Search (AI Concept Matching)":
        with st.spinner("Analyzing semantics..."):
            for concept in search_concepts:
                query_vector = vectorizer_model.transform([concept])
                
                from sklearn.preprocessing import normalize
                normalized_embeddings = normalize(embeddings, norm='l2', axis=1)
                normalized_query = normalize(query_vector, norm='l2', axis=1)
                
                similarities = (normalized_embeddings * normalized_query.T).toarray().squeeze()
                
                matching_indices = np.where(similarities >= similarity_threshold)[0]
                
                if len(matching_indices) > 0:
                    concept_df = df_vars.iloc[matching_indices].copy()
                    concept_df['SIMILARITY'] = similarities[matching_indices]
                    concept_df['MATCHED_CONCEPT'] = concept
                    matched_vars_by_concept.append(concept_df)
                    
        if matched_vars_by_concept:
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
    
    # Count RDC matches before we potentially filter them out
    rdc_match_count = matched_vars[matched_vars['RDC_ONLY'] == True]['TABLE'].nunique()
    
    # Filter the DataFrame based on the sidebar setting
    if not show_rdc:
        matched_vars = matched_vars[matched_vars['RDC_ONLY'] == False]
    
    # Display the concise warning in the sidebar if showing RDC tables and matches exist
    if show_rdc and rdc_match_count > 0:
        st.sidebar.warning(
            "⚠️ **Note:** Tables that require Research Data Center (RDC) access (highlighted in red) "
            "will not be included in the auto-generated code snippet."
        )

    # Re-evaluate empty check after potential filter
    if not matched_vars.empty:
        distinct_tables_count = matched_vars['TABLE'].nunique()
        st.success(
            f"Found **{len(matched_vars)}** matching variables across **{distinct_tables_count}** distinct tables!"
        )

        # Sort results to place best semantic hits at the top
        if 'SIMILARITY' in matched_vars.columns:
            matched_vars = matched_vars.sort_values(by='SIMILARITY', ascending=False)
        
        # Build selection list excluding RDC tables completely
        unique_tables = sorted(matched_vars['TABLE'].unique())
        downloadable_tables = [t for t in unique_tables if t not in rdc_tables]
        
        selected_tables = st.multiselect(
            "Choose NHANES tables to bundle into download package:",
            options=downloadable_tables,
            default=downloadable_tables[:5] if len(downloadable_tables) > 0 else []
        )
        
        # Apply soft-red conditional styling to RDC rows
        def style_rdc_rows(row):
            color = 'background-color: #ffebee' if row['RDC_ONLY'] else ''
            return [color] * len(row)
        
        styled_df = matched_vars.style.apply(style_rdc_rows, axis=1)
        
        # Display styled dataframe, hiding the control columns
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
        st.warning("All matches require RDC authorization. Adjust 'Display RDC-only tables' in the sidebar to view them.")
else:
    if search_input.strip():
        st.warning("No variables matched your search parameters.")

# -------------------------------------------------------------
# 5. Demographics Bundling & Python Code Generation
# -------------------------------------------------------------
if selected_tables:
    st.write("---")
    st.write("### 📦 Step 2: Configure Bundle & Retrieve")
    
    include_demos = st.checkbox(
        "💡 **Auto-include corresponding Demographics tables**", 
        value=True,
        help="Recommended. This auto-resolves the demographics table for each selected table's cycle so you can merge them later."
    )
    
    final_download_list = list(selected_tables)
    
    if include_demos:
        demo_additions = []
        for table in selected_tables:
            row = df_tables[df_tables['TABLE'] == table]
            if not row.empty:
                begin_year = int(row.iloc[0]['BEGINYEAR'])
                if begin_year == 1999:
                    demo_table = "DEMO"
                else:
                    cycle_letter = chr(65 + int((begin_year - 1999) / 2))
                    demo_table = f"DEMO_{cycle_letter}"
                
                if demo_table not in final_download_list and demo_table not in demo_additions:
                    demo_additions.append(demo_table)
        
        final_download_list.extend(demo_additions)
        if demo_additions:
            st.info(f"Adding demographic baselines: `{', '.join(demo_additions)}`")

    st.write("**Your Final Data Package List:**")
    st.code(", ".join(final_download_list))
    
    # Generate the Easy Python Retrieval Code
    st.write("#### 🐍 Step 3: Copy Code to Python")
    st.write("Because the CDC servers limit Streamlit web-scraping speed, use this optimized snippet to load these files directly into your local Python environment:")
    
    # Generate copy-pasteable script utilizing a precise cycle dictionary map
    python_snippet = f"""import pandas as pd
import urllib.request
import traceback

# List of NHANES tables identified via NHANES Scout
tables_to_load = ['SPX_E', 'SPX_F', 'SPX_G', 'DEMO_E', 'DEMO_F', 'DEMO_G']

def fetch_nhanes_tables(table_list):
    cycle_map = {
        '_A': '1999-2000', '_B': '2001-2002', '_C': '2003-2004', 
        '_D': '2005-2006', '_E': '2007-2008', '_F': '2009-2010', 
        '_G': '2011-2012', '_H': '2013-2014', '_I': '2015-2016', 
        '_J': '2017-2018', '_K': '2019-2020', '_L': '2021-2023',
        '_M': '2023-2024'
    }
    
    datasets = {}
    for table in table_list:
        print("\n" + "="*50)
        print(f"📋 TARGET TABLE: {table}")
        
        # Determine the target cycle folder
        suffix = next((s for s in cycle_map if table.endswith(s)), None)
        cycle_folder = cycle_map[suffix] if suffix else '1999-2000'
        
        # Build primary and alternative urls using lower case '.xpt'
        url_primary = f"https://wwwn.cdc.gov/Nchs/Nhanes/{cycle_folder}/{table}.xpt"
        url_alt = f"https://wwwn.cdc.gov/Nchs/Nhanes/Demographics/{table}.xpt"
        
        success = False
        for path_type, url in [("Primary Path", url_primary), ("Alternative Path", url_alt)]:
            print(f"   🔍 Checking {path_type}: {url}")
            try:
                # HTTP Preflight Diagnostic check to inspect headers before loading
                req = urllib.request.Request(url, method='HEAD')
                with urllib.request.urlopen(req) as response:
                    content_type = response.headers.get('Content-Type', '')
                    print(f"   📡 Server Response Code: {response.status}")
                    print(f"   📄 Content Type Returned: '{content_type}'")
                
                # Attempt to parse data stream
                datasets[table] = pd.read_sas(url)
                print(f"   ✅ SUCCESS: Loaded {len(datasets[table])} rows.")
                success = True
                break  # Skip alternative path if primary works
                
            except Exception as e:
                print(f"   ⚠️ Blocked on {path_type}!")
                print(f"      Error Details: {str(e).strip()}")
                
        if not success:
            print(f"❌ CRITICAL: Could not fetch {table} from either path.")
            
    return datasets

nhanes_data = fetch_nhanes_tables(tables_to_load)
"""
    st.code(python_snippet, language="python")
