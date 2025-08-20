import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import MinMaxScaler, Normalizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import hstack
import pickle

df = pd.read_csv('games.csv')
df['features_text'] = df["genres"].fillna('') + " " + df["tags"].fillna('')

# Text features (reduce to ~300 to avoid sparsity)
vectorizer = TfidfVectorizer(max_features=300, stop_words="english")
X_text = vectorizer.fit_transform(df["features_text"])

# Numeric features
scaler = MinMaxScaler()
X_num = scaler.fit_transform(df[["rating", "metacritic"]].fillna(0))

# Combine
X = hstack([X_text, X_num])

# Dimensionality reduction (stable with small sample)
svd = TruncatedSVD(n_components=50, random_state=42)
normalizer = Normalizer(copy=False)
X_red = normalizer.fit_transform(svd.fit_transform(X))

kmeans = KMeans(n_clusters=8, random_state=42, n_init="auto")
df["cluster"] = kmeans.fit_predict(X_red)

# print(df[["name", "genres", "rating", "cluster"]].head(10))

similarity = cosine_similarity(X_red)

with open("model.pkl", "wb") as f:
    pickle.dump((df, vectorizer, scaler, svd, normalizer, kmeans, similarity), f)

# print(recommend_games("Grand Theft Auto V")['name'])
