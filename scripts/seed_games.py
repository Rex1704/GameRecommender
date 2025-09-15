import os
import requests
from datetime import datetime
from app import db
from app.models import Game
from PIL import Image
import requests as req
from io import BytesIO
from colorthief import ColorThief

# Get RAWG API key
RAWG_API_KEY = os.getenv("RAWG_API_KEY")  # set in .env / Render dashboard
BASE_URL = "https://api.rawg.io/api/games"

def extract_accent_color(image_url):
    """Extract dominant RGB color from an image."""
    try:
        response = req.get(image_url, timeout=10)
        if response.status_code != 200:
            return None
        img = BytesIO(response.content)
        color_thief = ColorThief(img)
        dominant_color = color_thief.get_color(quality=1)
        return ",".join(map(str, dominant_color))  # store as "r,g,b"
    except Exception as e:
        print(f"Accent color failed for {image_url}: {e}")
        return None

def fetch_games(page_size=40, max_games=1000):
    """Fetch games from RAWG API in pages."""
    page = 1
    total_fetched = 0
    while total_fetched < max_games:
        params = {
            "key": RAWG_API_KEY,
            "page_size": page_size,
            "page": page,
        }
        resp = requests.get(BASE_URL, params=params)
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        for game in results:
            yield game
            total_fetched += 1
            if total_fetched >= max_games:
                return
        page += 1

def seed_games():
    count_before = Game.query.count()
    print(f"Games in DB before: {count_before}")

    for rawg_game in fetch_games(max_games=1000):
        if Game.query.filter_by(slug=rawg_game["slug"]).first():
            continue  # skip duplicates

        accent_color = extract_accent_color(rawg_game.get("background_image")) if rawg_game.get("background_image") else None

        game = Game(
            id=rawg_game["id"],
            slug=rawg_game["slug"],
            name=rawg_game["name"],
            description=rawg_game.get("description", ""),
            released=datetime.strptime(rawg_game["released"], "%Y-%m-%d").date() if rawg_game.get("released") else None,
            rating=rawg_game.get("rating"),
            metacritic=rawg_game.get("metacritic"),
            genres=",".join([g["name"] for g in rawg_game.get("genres", [])]),
            tags=",".join([t["name"] for t in rawg_game.get("tags", [])]),
            background_image=rawg_game.get("background_image"),
            playtime=rawg_game.get("playtime"),
            accent_color=accent_color,
            last_updated=datetime.now(),
        )
        db.session.add(game)

    db.session.commit()
    count_after = Game.query.count()
    print(f"Games in DB after: {count_after}")

if __name__ == "__main__":
    seed_games()
