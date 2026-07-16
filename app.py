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
# Import this at the very top of your app.py along with other libraries
from scipy.sparse import load_npz, csr_matrix

@st.cache_data
def load_vector_embeddings(emb_mtime):
    # Change target file extension to .npz
    emb_path = "cache_vector_embeddings.npz"
    if os.path.exists(emb_path):
        return load_npz(emb_path)
    return None

# Update modification tracking file target at the bottom of Section 1:
emb_mtime = os.path.getmtime("cache_vector_embeddings.npz") if os.path.exists("cache_vector_embeddings.npz") else 0

# -------------------------------------------------------------
# 2. Search & Filter Engine (Smart Phrasing & Comma Separation)
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
                
                # Filter variables that hit at least a 15% similarity score
                threshold = 0.15
                matching_indices = np.where(similarities >= threshold)[0]
                
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
