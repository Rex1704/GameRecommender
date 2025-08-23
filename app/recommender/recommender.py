import pickle, os
import numpy as np
import pandas as pd
import re

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_PATH, "..", "data", "model.pkl")
DETAILS_PATH = os.path.join(BASE_PATH, "..", "data", "game_details.csv")

with open(MODEL_PATH, "rb") as f:
    df, vectorizer, scaler, svd, normalizer, kmeans, similarity = pickle.load(f)

if os.path.exists(DETAILS_PATH):
    details_df = pd.read_csv(DETAILS_PATH)
else:
    details_df = pd.DataFrame()

# ---- Helpers ----
def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", "", (s or "").lower()).strip()

def extract_franchise_key(name: str, slug: str) -> str:
    """
    Heuristic: use slug base (strip trailing numbers/words like remastered, definitive, goty)
    and also fallback to first 2-3 tokens of name if needed.
    """
    s = (slug or _norm_text(name or ""))
    # remove edition words
    s = re.sub(r"-(remastered|definitive|complete|goty|ultimate|hd|vr|redux)$", "", s)
    # remove trailing numbers (ii, iii, 2, 3, 2020 etc.)
    s = re.sub(r"-(\d+|[ivx]+)$", "", s)
    # compress multiple dashes
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

# Quick index lookups
ID_TO_INDEX = {
    int(row.id): idx
    for idx, row in enumerate(df[["id"]].itertuples(index=False))
}
INDEX_TO_ID = df["id"].to_numpy()

# ---- Public API for app ----
def get_diverse_feed(n=60):
    n = min(n, len(df))
    return _enrich_with_details(df.sample(n).to_dict(orient="records"))

def diverse_popular_feed():
    genres = df["genres"].dropna().str.split(", ")
    all_genres = sorted({g for sub in genres for g in sub})
    recs = []
    for g in all_genres[:10]:  # pick top 10 genres to keep it light
        mask = df["genres"].apply(lambda x: g in x if isinstance(x, str) else False)
        top = df[mask].nlargest(5, "rating", "all")  # top 5 per genre
        top = top.drop_duplicates(subset=['id'])
        recs.extend(top.to_dict(orient="records"))

    return _enrich_with_details(recs)

def recommend_similar_games(game_id: int, n=20, within_cluster_first=True):
    if game_id not in df["id"].values:
        return get_diverse_feed(n)
    idx = ID_TO_INDEX[int(game_id)]
    sims = similarity[idx]  # 1D np.array
    order = np.argsort(-sims)

    # Optional: prefer same KMeans cluster first
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
    avg_sim = np.mean(similarity[idxs], axis=0)
    return avg_sim.astype(np.float32)

def _enrich_with_details(games: list[dict]) -> list[dict]:
    """Merge details (image, description, etc.) from details_df into the list of games."""
    if details_df.empty:
        return games
    merged = []
    for g in games:
        extra = details_df[details_df["slug"] == g.get("slug")]
        if not extra.empty:
            g = {**g, **extra.iloc[0].to_dict()}
        merged.append(g)
    return merged


def hybrid_recommend(
    clicked_ids: list[int] | None,
    played_ids: list[int] | None,
    n=60,
    w_content=0.6,
    w_franchise=0.25,
    w_pop=0.15,
    exclude_played=True,
    diversify=True,
):
    clicked_ids = clicked_ids or []
    played_ids = played_ids or []

    # Scores
    s_content = _content_profile_sim(clicked_ids)
    s_franchise = _franchise_boost_vector(played_ids, weight=1.0)
    s_pop = POP_SCORES

    # Weighted sum
    score = w_content * s_content + w_franchise * s_franchise + w_pop * s_pop

    # Exclude games the user already marked as played
    mask_excl = np.ones(len(df), dtype=bool)
    if exclude_played and played_ids:
        for pid in played_ids:
            if pid in ID_TO_INDEX:
                mask_excl[ID_TO_INDEX[pid]] = False

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
    row = df[df["id"] == game_id]
    if row.empty:
        return {}
    game = row.iloc[0].to_dict()
    if not details_df.empty:
        more = details_df[details_df["slug"] == game.get("slug")]
        if not more.empty:
            game.update(more.iloc[0].to_dict())
    return game
