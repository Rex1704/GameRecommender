import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time

load_dotenv()
API_KEY = os.getenv("RAWG_API_KEY")

BASE_URL = "https://api.rawg.io/api"
PARAMS = {"key": API_KEY}

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
GAMES_PATH = os.path.join(BASE_PATH, "..", "app", "data", "games.csv")
DETAILS_PATH = os.path.join(BASE_PATH, "..", "app", "data", "game_details.csv")

def fetch_games(n=1000, filename=GAMES_PATH):
    """Fetch basic game info into games.csv with resume support"""
    games = []

    # Load already collected games
    if os.path.exists(filename):
        existing = pd.read_csv(filename)
        collected_ids = set(existing["id"].tolist())
        games = existing.to_dict(orient="records")
        print(f"Resuming from {len(existing)} games already collected.")
    else:
        collected_ids = set()

    page = 1
    collected = len(collected_ids)

    while collected < n:
        url = f"{BASE_URL}/games"
        params = {**PARAMS, "page": page, "page_size": 40}
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching page {page}: {e}, retrying in 5s...")
            time.sleep(5)
            continue

        results = data.get("results", [])
        if not results:
            break

        for g in results:
            if g.get("id") in collected_ids:
                continue  # skip duplicates

            games.append({
                "id": g.get("id"),
                "name": g.get("name"),
                "slug": g.get("slug"),
                "released": g.get("released"),
                "rating": g.get("rating"),
                "metacritic": g.get("metacritic"),
                "genres": ", ".join([gen["name"] for gen in g.get("genres", [])]),
                "tags": ", ".join([tag["name"] for tag in g.get("tags", [])]),
                "platforms": ", ".join([p["platform"]["name"] for p in g.get("platforms", []) if p.get("platform")]),
            })
            collected_ids.add(g.get("id"))

        collected = len(collected_ids)
        print(f"Collected {collected}/{n} games...")
        page += 1
        time.sleep(1)  # prevent rate limit

        # Save progress every 200 games
        if collected % 200 == 0:
            pd.DataFrame(games).to_csv(filename, index=False, encoding="utf-8")
            print("💾 Progress saved.")

    pd.DataFrame(games).to_csv(filename, index=False, encoding="utf-8")
    print("✅ Saved games.csv")
    return pd.DataFrame(games)


def fetch_game_details(slugs, filename=DETAILS_PATH):
    """Fetch detailed info for games into game_details.csv with resume support"""
    details = []

    # Load already collected details
    if os.path.exists(filename):
        existing = pd.read_csv(filename)
        collected_slugs = set(existing["slug"].dropna().tolist())
        details = existing.to_dict(orient="records")
        print(f"Resuming from {len(existing)} game details already collected.")
    else:
        collected_slugs = set()

    for i, slug in enumerate(slugs, 1):
        if slug in collected_slugs:
            continue  # skip already done

        url = f"{BASE_URL}/games/{slug}"
        try:
            response = requests.get(url, params=PARAMS, timeout=10)
            response.raise_for_status()
            g = response.json()
        except Exception as e:
            print(f"Error fetching details for {slug}: {e}, skipping...")
            continue

        details.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "slug": g.get("slug"),
            "description": g.get("description_raw"),
            "playtime": g.get("playtime"),
            "released": g.get("released"),
            "rating": g.get("rating"),
            "metacritic": g.get("metacritic"),
            "genres": ", ".join([gen["name"] for gen in g.get("genres", [])]),
            "tags": ", ".join([tag["name"] for tag in g.get("tags", [])]),
            "platforms": ", ".join([p["platform"]["name"] for p in g.get("platforms", []) if p.get("platform")]),
            "background_image": g.get("background_image"),
            "website": g.get("website"),
        })

        collected_slugs.add(slug)

        if i % 50 == 0:
            print(f"Fetched details for {i} games...")
            pd.DataFrame(details).to_csv(filename, index=False, encoding="utf-8")
            print("💾 Progress saved.")

        time.sleep(1)  # avoid rate limit

    pd.DataFrame(details).to_csv(filename, index=False, encoding="utf-8")
    print("✅ Saved game_details.csv")
    return pd.DataFrame(details)


if __name__ == "__main__":
    # Step 1: Collect basic game info
    games_df = pd.read_csv(GAMES_PATH)
    #
    # # Step 2: Collect details for each game (based on slugs)
    # slugs = games_df["slug"].dropna().unique().tolist()
    # details_df = fetch_game_details(slugs, filename=DETAILS_PATH)
    url = f"{BASE_URL}/games/{games_df['slug'][0]}"
    g = ""
    try:
        response = requests.get(url, params=PARAMS, timeout=10)
        response.raise_for_status()
        g = response.json()
    finally:
        print(g)
