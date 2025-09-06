# populate_colors.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from PIL import Image
import requests
from io import BytesIO
import os
from dotenv import load_dotenv

load_dotenv()

# Import your Game model
from app.models import Game

# Set up your database connection
engine = create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)
session = Session()


def get_dominant_color(image_url):
    """Fetches an image from a URL and returns its average color."""
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        img.thumbnail((100, 100))
        img = img.convert("RGB")
        colors = list(img.getdata())

        r = sum(c[0] for c in colors)
        g = sum(c[1] for c in colors)
        b = sum(c[2] for c in colors)
        count = len(colors)

        return f"{r // count}, {g // count}, {b // count}"
    except Exception as e:
        print(f"Error processing image at {image_url}: {e}")
        return None


def update_game_colors():
    """Iterates through games and updates the color column."""
    try:
        # Query for all games
        games = session.query(Game).all()

        for game in games:
            # Assume each game has a thumbnail_url column
            if game.background_image:
                color = get_dominant_color(game.background_image)
                if color:
                    game.accent_color = color
                    print(f"Updated color for '{game.name}': {color}")

        # Commit all changes to the database
        session.commit()
        print("Successfully updated all game colors.")
    except Exception as e:
        session.rollback()
        print(f"An error occurred: {e}")
    finally:
        session.close()


if __name__ == '__main__':
    update_game_colors()