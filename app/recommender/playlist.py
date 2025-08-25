import os
import re
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from app.recommender.recommender import df, extract_franchise_key

CACHE_FILE = os.path.join(os.path.dirname(__file__), "franchise_cache.json")

# Load cache from disk
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        FRANCHISE_CACHE = json.load(f)
else:
    FRANCHISE_CACHE = {}

# ✅ Optional curated overrides for tricky franchises
STORY_OVERRIDES = {
    "final-fantasy": [
        "final fantasy vii",
        "final fantasy vii remake",
        "final fantasy viii",
        "final fantasy ix",
    ],
    "zelda": [
        "the legend of zelda: ocarina of time",
        "the legend of zelda: majora's mask",
        "the legend of zelda: twilight princess",
    ],
}

def save_cache():
    """Save franchise order cache to disk."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(FRANCHISE_CACHE, f, indent=2, ensure_ascii=False)

def fetch_franchise_order(franchise_title: str) -> list[str]:
    """
    Try to fetch release order of a franchise from Wikipedia list page.
    Uses cache to avoid redundant requests.
    """
    # 1. If cached, return
    if franchise_title in FRANCHISE_CACHE:
        return FRANCHISE_CACHE[franchise_title]

    url = f"https://en.wikipedia.org/wiki/{franchise_title.replace(' ', '_')}"
    order = []
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    for li in soup.select("li"):
        text = li.get_text(" ", strip=True)
        if len(text) > 4 and not text.lower().startswith("list of"):
            order.append(text.lower())

    # Save to cache
    FRANCHISE_CACHE[franchise_title] = order
    save_cache()

    return order

def assign_franchise_order(sub_df: pd.DataFrame, franchise_key: str) -> pd.DataFrame:
    """
    Assign an `order_index` for games inside one franchise.
    Uses overrides > Wikipedia > release year > numeric suffix heuristic.
    """
    order = []

    # 1. Check manual overrides
    if franchise_key in STORY_OVERRIDES:
        order = STORY_OVERRIDES[franchise_key]

    # 2. Try Wikipedia
    if not order:
        wiki_key = f"List_of_{franchise_key.replace('-', '_')}_video_games"
        order = fetch_franchise_order(wiki_key)

    # 3. Assign order_index
    if order:
        mapping = {name: i for i, name in enumerate(order)}
        sub_df["order_index"] = sub_df["name"].str.lower().map(mapping).fillna(float("inf"))
    else:
        # 4. Fallback: release year
        if "released" in sub_df.columns and sub_df["released"].notna().any():
            years = pd.to_datetime(sub_df["released"], errors="coerce").dt.year
            sub_df["order_index"] = years.fillna(9999)
        else:
            # 5. Fallback: numeric suffix heuristic
            def suffix_num(name):
                name = name.lower()
                m = re.search(r"(\d+|ii|iii|iv|v|vi|vii|viii|ix|x)\b", name)
                if not m:
                    return 9999
                token = m.group(1)
                roman_map = {
                    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
                    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
                }
                return roman_map.get(token, int(token)) if token.isdigit() or token in roman_map else 9999
            sub_df["order_index"] = sub_df["name"].map(suffix_num)

    return sub_df.sort_values("order_index").reset_index(drop=True)

def optimize_play_order(game_ids: list[int]) -> list[dict]:
    """
    Given list of game IDs (user's To-Play list),
    return an optimized play order that:
      - Groups by franchise
      - Orders sequels intelligently
      - Adds variety across franchises
    """
    if not game_ids:
        return []

    sub_df = df[df["id"].isin(game_ids)].copy()
    if sub_df.empty:
        return []

    # Assign franchise key
    sub_df["franchise_key"] = sub_df.apply(
        lambda r: extract_franchise_key(r["name"], r.get("slug", "")),
        axis=1
    )

    ordered_games = []
    for key, group in sub_df.groupby("franchise_key"):
        ordered = assign_franchise_order(group, key)
        ordered_games.extend(ordered.to_dict(orient="records"))

    # ---- Fun Maximization Layer ----
    franchise_groups = {}
    for g in ordered_games:
        franchise_groups.setdefault(g["franchise_key"], []).append(g)

    final_order = []
    while any(franchise_groups.values()):
        for key in list(franchise_groups.keys()):
            if franchise_groups[key]:
                final_order.append(franchise_groups[key].pop(0))

    return final_order
