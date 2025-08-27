import pickle, os
import numpy as np
import pandas as pd
from app.models import Game
import re

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_PATH, "..", "data", "model.pkl")

with open(MODEL_PATH, "rb") as f:
    df, vectorizer, scaler, svd, normalizer, kmeans, similarity = pickle.load(f)


# ---- Helpers ----
def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", "", (s or "").lower()).strip()

def extract_franchise_key(name: str, slug: str) -> str:
    s = (slug or _norm_text(name or ""))
    s = re.sub(r"-(remastered|definitive|complete|goty|ultimate|hd|vr|redux)$", "", s)
    s = re.sub(r"-(\d+|[ivx]+)$", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        tokens = _norm_text(name).split()
        s = "-".join(tokens[:3])
    return s

def build_franchise_index(_df: pd.DataFrame):
    keys = _df.apply(lambda r: extract_franchise_key(r["name"], r.get("slug", "")), axis=1)
    mapping = {}
    for idx, key in enumerate(keys):
        mapping.setdefault(key, set()).add(_df.iloc[idx]["id"])
    return mapping

FRANCHISE_INDEX = build_franchise_index(df)

# Popularity prior: combine rating & metacritic → z-score → [0,1]
def _popularity_scores(_df: pd.DataFrame):
    pop = _df[["rating", "metacritic"]].copy()
    for col in ["rating", "metacritic"]:
        if col not in pop.columns:
            pop[col] = np.nan
    pop = pop.fillna(pop.mean())
    z = (pop - pop.mean()) / (pop.std(ddof=0) + 1e-9)
    s = z.mean(axis=1)
    s = (s - s.min()) / (s.max() - s.min() + 1e-9)
    return s.values

POP_SCORES = _popularity_scores(df)

POP_SCORES = _popularity_scores(df)

# Quick index lookups
ID_TO_INDEX = {int(row.id): idx for idx, row in enumerate(df[["id"]].itertuples(index=False))}
INDEX_TO_ID = df["id"].to_numpy()

# ---- Public API for app ----
def get_diverse_feed(n=60):
    n = min(n, len(df))
    return _enrich_with_details(df.sample(n).to_dict(orient="records"))

def recommend_similar_games(game_id: int, n=20, within_cluster_first=True):
    if game_id not in df["id"].values:
        return get_diverse_feed(n)
    idx = ID_TO_INDEX[int(game_id)]
    sims = similarity[idx]
    order = np.argsort(-sims)

    if within_cluster_first and "cluster" in df.columns:
        c = df.iloc[idx].get("cluster")
        same = [i for i in order if df.iloc[i].get("cluster") == c and INDEX_TO_ID[i] != game_id]
        rest = [i for i in order if INDEX_TO_ID[i] != game_id and i not in same]
        final = (same + rest)[:n]
    else:
        final = [i for i in order if INDEX_TO_ID[i] != game_id][:n]

    return _enrich_with_details(df.iloc[final].to_dict(orient="records"))



def _franchise_boost_vector(played_ids: list[int], weight=1.0):
    """Return a 1D array (len=df) with boosts for titles in same franchise as any played."""
    boost = np.zeros(len(df), dtype=np.float32)
    if not played_ids:
        return boost
    keys = set()
    for pid in played_ids:
        if pid not in ID_TO_INDEX:
            continue
        row = df.iloc[ID_TO_INDEX[pid]]
        keys.add(extract_franchise_key(row["name"], row.get("slug", "")))
    candidate_ids = set()
    for k in keys:
        candidate_ids |= FRANCHISE_INDEX.get(k, set())
    # small boost for those candidates
    idxs = [ID_TO_INDEX[i] for i in candidate_ids if i in ID_TO_INDEX]
    boost[idxs] = weight
    return boost


def _content_profile_sim(clicked_ids: list[int]) -> np.ndarray:
    """Average similarity of clicked games → 1D score per game."""
    idxs = [ID_TO_INDEX[cid] for cid in clicked_ids if cid in ID_TO_INDEX]
    if not idxs:
        return np.zeros(len(df), dtype=np.float32)

    decay = 0.8  # more decay = older clicks contribute less
    weights = [decay ** (len(idxs) - 1 - i) for i in range(len(idxs))]

    sims = np.vstack([similarity[i] * w for i, w in zip(idxs, weights)])
    avg_sim = np.mean(sims, axis=0)
    return avg_sim.astype(np.float32)

def _enrich_with_details(games: list[dict]) -> list[dict]:
    if not games:
        return games

    ids = [g["id"] for g in games if "id" in g]
    db_games = {g.id: g for g in Game.query.filter(Game.id.in_(ids)).all()}

    return [
        {**g, **db_games[g["id"]].to_dict()} if g["id"] in db_games else g
        for g in games
    ]




def _rating_boost_vector(user_ratings: dict, weight=1.0):
    """Turn user ratings into weighted score boosts."""
    boost = np.zeros(len(df), dtype=np.float32)
    if not user_ratings:
        return boost

    for gid, rating in user_ratings.items():
        if int(gid) not in ID_TO_INDEX:
            continue
        idx = ID_TO_INDEX[int(gid)]
        # normalize rating (1–5 → -1 to +1)
        norm = (rating - 3) / 2.0
        boost += norm * similarity[idx] * weight
    return boost


def hybrid_recommend(
    clicked_ids: list[int] | None,
    played_ids: list[int] | None,
    user_ratings: dict[str:int] | None,
    n=60,
    w_content=0.5,
    w_franchise=0.2,
    w_pop=0.1,
    w_rating=0.2,
    diversify=True,
):
    clicked_ids = clicked_ids or []
    played_ids = played_ids or []
    user_ratings = user_ratings or {}

    # Scores
    s_content = _content_profile_sim(clicked_ids)
    s_franchise = _franchise_boost_vector(played_ids, weight=1.0)
    s_pop = POP_SCORES
    s_rating = _rating_boost_vector(user_ratings, weight=1.0)

    # Weighted sum
    score = w_content * s_content + w_franchise * s_franchise + w_pop * s_pop + w_rating * s_rating

    # Exclude games the user already marked as played
    mask_excl = np.ones(len(df), dtype=bool)
    if played_ids:
        for pid in played_ids:
            if pid in ID_TO_INDEX:
                idx = ID_TO_INDEX[pid]
                score[idx] *= 0.3

    # Rank
    order = np.argsort(-score)
    order = [i for i in order if mask_excl[i]]

    # Optional: diversify by limiting per-franchise count
    if diversify:
        taken, out, limit = set(), [], 3
        for i in order:
            row = df.iloc[i]
            key = extract_franchise_key(row["name"], row.get("slug", ""))
            cnt = sum(1 for j in out if extract_franchise_key(df.iloc[j]["name"], df.iloc[j].get("slug", "")) == key)
            if cnt < limit:
                out.append(i)
            if len(out) >= n:
                break
        final = out
    else:
        final = order[:n]


    return _enrich_with_details(df.iloc[final].to_dict(orient="records"))


def get_game_detail(game_id: int) -> dict:
    game = Game.query.get(game_id)
    return game.to_dict() if game else {}

