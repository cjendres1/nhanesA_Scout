# make_embeddings.py
import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import save_npz

print("Loading local cache variables...")
df_vars = pd.read_csv("cache_variables_manifest.csv")
df_vars.columns = [col.upper() for col in df_vars.columns]

# Target description column safely
desc_col = 'VARDESC' if 'VARDESC' in df_vars.columns else ('DESCRIPTION' if 'DESCRIPTION' in df_vars.columns else df_vars.columns[1])
df_vars[desc_col] = df_vars[desc_col].fillna("").astype(str)

print("Fitting TF-IDF Vectorizer...")
vectorizer = TfidfVectorizer(
    stop_words='english',
    sublinear_tf=True,
    strip_accents='unicode'
)

# Learn the vocabulary and extract variable coordinate vectors
descriptions = df_vars[desc_col].tolist()
# Keep it as a highly efficient scipy sparse matrix instead of forcing it to a dense array (.toarray())
sparse_embeddings = vectorizer.fit_transform(descriptions)

# Save the sparse matrix in a super-compressed format (.npz)
save_npz("cache_vector_embeddings.npz", sparse_embeddings)

# Save the vocabulary structure
with open("cache_vectorizer.pkl", "wb") as f:
    pickle.dump(vectorizer, f)

print("Success! Compressed output saved:")
print(f" - 'cache_vector_embeddings.npz' (Sparse matrix representation)")
print(" - 'cache_vectorizer.pkl' (Fitted vocabulary mapping)")
