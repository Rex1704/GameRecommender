import os
import time
import requests
from io import BytesIO
from dotenv import load_dotenv
from app import create_app, db
from app.models import Game  # your SQLAlchemy Game model
import cloudinary.uploader
import cloudinary
import json

# Load environment variables
load_dotenv()
API_KEY = os.getenv("RAWG_API_KEY")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")



cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

BASE_URL = "https://api.rawg.io/api"

app = create_app()
app.app_context().push()

def upload_to_cloudinary(image_url, game_id):
    """Upload image to Cloudinary in WebP and return the secure URL"""
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    img_bytes = BytesIO(response.content)

    result = cloudinary.uploader.upload(
        img_bytes,
        public_id=f"games/{game_id}/original",
        overwrite=True,
        resource_type="image",
        format="webp"  # force WebP (can use 'avif' too if supported)
    )
    return result["secure_url"]

def fetch_and_update_game_screenshots():
    games = Game.query.all()
    for i, game in enumerate(games, 1):
        print(f"[{i}] Processing {game.name}...")

        # Skip if screenshots already exist
        if game.screenshots:
            print(" - Screenshots already exist, skipping.")
            continue

        # Fetch screenshots from RAWG
        try:
            url = f"{BASE_URL}/games/{game.id}/screenshots"
            response = requests.get(url, params={"key": API_KEY}, timeout=10)
            response.raise_for_status()
            data = response.json()
            raw_screenshots = [s["image"] for s in data.get("results", [])]
        except Exception as e:
            print(f" - Failed to fetch screenshots for {game.name}: {e}")
            continue

        if not raw_screenshots:
            print(" - No screenshots found.")
            continue

        # Upload screenshots to Cloudinary
        cloud_screenshots = []
        for idx, shot_url in enumerate(raw_screenshots, 1):
            public_id = f"games/{game.id}/screenshot_{idx}"
            uploaded_url = upload_to_cloudinary(shot_url, public_id)
            if uploaded_url:
                cloud_screenshots.append(uploaded_url)
            time.sleep(0.2)  # avoid spamming RAWG or Cloudinary

        # Update game record
        if cloud_screenshots:
            game.screenshots = json.dumps(cloud_screenshots)  # or use JSON type if Postgres
            db.session.commit()
            print(f" - Uploaded {len(cloud_screenshots)} screenshots for {game.name}")

        time.sleep(0.4)

def update_game_descriptions_and_images():
    games = Game.query.all()
    for i, game in enumerate(games, 1):
        # Skip if already has description and image_url
        if game.description:
            continue

        # Fetch description from RAWG
        try:
            url = f"{BASE_URL}/games/{game.slug}"
            response = requests.get(url, params={"key": API_KEY}, timeout=10)
            response.raise_for_status()
            data = response.json()
            description = data.get("description_raw", "")
        except Exception as e:
            print(f"[{i}] Failed to fetch description for {game.slug}: {e}")
            continue

        # Upload background_image to Cloudinary if exists
        image_url = None
        if data.get("background_image"):
            try:
                image_url = upload_to_cloudinary(data["background_image"], game.id)
            except Exception as e:
                print(f"[{i}] Failed to upload image for {game.slug}: {e}")

        # Update DB
        game.description = description
        if image_url:
            game.background_image = image_url

        db.session.commit()
        print(f"[{i}] Updated {game.name} (description + image_url)")

        # Avoid hitting RAWG rate limit
        time.sleep(0.5)

if __name__ == "__main__":
    # update_game_descriptions_and_images()
    # game_id = 39707 # example game ID
    #
    # url = f"https://api.rawg.io/api/games/{game_id}/screenshots"
    # response = requests.get(url, params={"key": API_KEY})
    # data = response.json()
    #
    # print(data)
    #
    # # Each screenshot object has 'id', 'image' (URL)
    # for shot in data["results"]:
    #     print(shot["image"])

    fetch_and_update_game_screenshots()

    print("✅ All done!")
