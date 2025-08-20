import requests
import pandas as pd
from dotenv import load_dotenv
import time
import os

load_dotenv()

API_KEY = os.getenv("RAWG_API_KEY")
BASE_URL = "https://api.rawg.io/api/games"

def fetch_games(pages=5):
    games = []
    for page in range(1, pages+1):
        url = f"{BASE_URL}?key={API_KEY}&page_size=40&page={page}"
        response = requests.get(url).json()
        for game in response['results']:
            games.append({
                "id": game["id"],
                "name": game["name"],
                "released": game.get("released", ""),
                "rating": game.get("rating", 0),
                "metacritic": game.get("metacritic", 0),
                "genres": ", ".join([g["name"] for g in game["genres"]]),
                "tags": ", ".join([t["name"] for t in game["tags"][:10]]),  # top 10 tags
                "image": game["background_image"]
            })
    return pd.DataFrame(games)

games = pd.read_csv("games.csv")


def name_to_slug(name):
    return name.lower().replace(":", "").replace(" ", "-").replace("'", "").replace(",", "").replace(".", "").replace(
        "!", "")


details = []
for _, row in games.iterrows():
    slug = name_to_slug(row["name"])
    url = f"{BASE_URL}/{slug}?key={API_KEY}"
    print(url)

    r = requests.get(url)
    if r.status_code != 200:
        print(f"Failed for {slug}")
        continue

    data = r.json()
    details.append({
        "id": data.get("id", ""),
        "slug": slug,
        "name": data.get("name", ""),
        "description": data.get("description_raw", ""),
        "genres": ", ".join([g["name"] for g in data.get("genres", [])]),
        "tags": ", ".join([t["name"] for t in data.get("tags", [])[:10]]),
        "released": data.get("released", ""),
        "rating": data.get("rating", 0),
        "platforms": ", ".join([p["platform"]["name"] for p in data.get("platforms", [])]),
        "image": data.get("background_image", "")
    })

    time.sleep(1)

df = pd.DataFrame(details)
df.to_csv("game_details.csv", index=False)
print("Saved game_details.csv")

# df = fetch_games(pages=10)  # ~400 games
# print(df.shape)
# df.to_csv("games.csv", index=False)
