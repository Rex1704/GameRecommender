# ml.py
import os
import pickle
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import StandardScaler, Normalizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity


# --------------------
# Load data
# --------------------
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_PATH, "..", "data", "model.pkl")
GAMES_PATH = os.path.join(BASE_PATH, "..", "data", "games.csv")
df = pd.read_csv(GAMES_PATH)

# --------------------
# Feature engineering
# --------------------
# Text: genres + tags
df["genres"] = df["genres"].fillna("")
df["tags"] = df.get("tags", "").fillna("")

df["text_features"] = df["genres"].astype(str) + " " + df["tags"].astype(str)

# Numeric features: rating, metacritic, release_year
df["rating"] = df.get("rating", np.nan).fillna(df.get("rating", np.nan).mean())
df["metacritic"] = df.get("metacritic", np.nan).fillna(df.get("metacritic", np.nan).mean())

if "released" in df.columns:
    df["release_year"] = pd.to_datetime(df["released"], errors="coerce").dt.year.fillna(0)
else:
    df["release_year"] = 0

numeric_features = df[["rating", "metacritic", "release_year"]].values

# --------------------
# Vectorization
# --------------------
print("Vectorizing text features...")
vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
X_text = vectorizer.fit_transform(df["text_features"])

# Dimensionality reduction
print("Reducing dimensions with SVD...")
svd = TruncatedSVD(n_components=100, random_state=42)
X_reduced = svd.fit_transform(X_text)

# Normalize text vectors
normalizer = Normalizer(copy=False)
X_text_final = normalizer.fit_transform(X_reduced)

# Scale numeric features
scaler = StandardScaler()
X_num = scaler.fit_transform(numeric_features)

# Combine text + numeric features
X_combined = np.hstack([X_text_final, X_num])

# --------------------
# Clustering
# --------------------
print("Clustering with KMeans...")
kmeans = KMeans(n_clusters=20, random_state=42, n_init=10)
df["cluster"] = kmeans.fit_predict(X_combined)

# --------------------
# Similarity matrix
# --------------------
print("Computing cosine similarity matrix...")
similarity = cosine_similarity(X_combined)

# --------------------
# Save model
# --------------------
with open(MODEL_PATH, "wb") as f:
    pickle.dump((df, vectorizer, scaler, svd, normalizer, kmeans, similarity), f)

print("✅ Training complete. Model saved as model.pkl")
