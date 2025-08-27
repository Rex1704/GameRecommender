import pandas as pd
from datetime import datetime
from app import create_app, db
from app.models import Game
import os

app = create_app()
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DETAILS_PATH = os.path.join(BASE_PATH, "..", "app", "data", "game_details.csv")
GAMES_PATH = os.path.join(BASE_PATH, "..", "app", "data", "games.csv")

def migrate_games():
    with app.app_context():
        # Load CSVs
        games_df = pd.read_csv(GAMES_PATH)
        details_df = pd.read_csv(DETAILS_PATH)

        # Merge on slug or id
        df = pd.merge(games_df, details_df, on="slug", how="left")
        for col in games_df.columns:
            if col in details_df.columns and col != "slug":
                df[col] = df[f"{col}_y"].combine_first(df[f"{col}_x"])
                df.drop([f"{col}_x", f"{col}_y"], axis=1, inplace=True)

        for _, row in df.iterrows():
            # Check if game already exists
            game = Game.query.filter_by(id=row["id"]).first()
            if not game:
                game = Game(id=row["id"], slug=row["slug"])

            # Update fields
            game.name = row.get("name")
            game.description = row.get("description")
            game.released = (
                datetime.strptime(row["released"], "%Y-%m-%d").date()
                if pd.notna(row.get("released"))
                else None
            )
            game.rating = row.get("rating") if pd.notna(row.get("rating")) else None
            game.metacritic = row.get("metacritic") if pd.notna(row.get("metacritic")) else None
            game.genres = row.get("genres")
            game.tags = row.get("tags")
            game.background_image = row.get("background_image")

            db.session.add(game)

        db.session.commit()
        print("✅ Migration complete!")

if __name__ == "__main__":
    migrate_games()
