import pickle, os
import numpy as np
import pandas as pd

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_PATH, "..", "data", "model.pkl")
DETAILS_PATH = os.path.join(BASE_PATH, "..", "data", "game_details.csv")

with open(MODEL_PATH, "rb") as f:
    df, vectorizer, scaler, svd, normalizer, kmeans, similarity = pickle.load(f)

details_df = pd.read_csv(DETAILS_PATH)

def get_diverse_feed(n=54):
    return df.sample(n).to_dict(orient="records")

def recommend_from_profile(clicked_ids, n=54):
    indices = [df[df["id"] == cid].index[0] for cid in clicked_ids if cid in df["id"].values]
    if not indices:
        return get_diverse_feed(n)

    avg_sim = np.mean(similarity[indices], axis=0)
    sim_scores = sorted(list(enumerate(avg_sim)), key=lambda x: x[1], reverse=True)

    rec_indices = [i for i, _ in sim_scores if df.iloc[i]["id"] not in clicked_ids][:n]
    return df.iloc[rec_indices].to_dict(orient="records")

def recommend_from_genres(genres, n=54):
    mask = df["genres"].apply(lambda g: any(gen in g for gen in genres))
    if mask.sum() == 0:
        return get_diverse_feed(n)
    return df[mask].sample(min(n, mask.sum())).to_dict(orient="records")

def get_game_detail(game_id):
    game = df[df["id"] == game_id].iloc[0].to_dict()
    details = details_df[details_df["name"] == game["name"]].to_dict(orient="records")
    if details:
        game.update(details[0])
    return game
