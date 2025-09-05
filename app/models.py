from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.types import PickleType
from datetime import datetime
from app import db
from flask_login import UserMixin

playlist_games = db.Table(
    "playlist_games",
    db.Column("playlist_id", db.Integer, db.ForeignKey("to_play_list.id"), primary_key=True),
    db.Column("game_id", db.Integer, db.ForeignKey("game.id"), primary_key=True),
    db.Column("position", db.Integer, nullable=False, default=0)
)


class ToPlayList(db.Model):
    __tablename__ = "to_play_list"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_user_playlist_name"),
    )

    games = db.relationship("Game", secondary="playlist_games", backref="playlists")

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # rawg ID
    slug = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    released = db.Column(db.Date)
    rating = db.Column(db.Float)
    metacritic = db.Column(db.Integer)
    genres = db.Column(db.String)        # comma-separated
    tags = db.Column(db.String)          # comma-separated
    background_image = db.Column(db.String)
    playtime = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    accent_color = db.Column(db.String(20))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "background_image": self.background_image,
            "description": self.description,
            "genres": self.genres,
            "tags": self.tags,
            "released": self.released,
            "metacritic": self.metacritic,
            "rating": self.rating,
            "playtime": self.playtime,
            "last_updated": self.last_updated,
            "accent_color": self.accent_color
        }

    def __repr__(self):
        return f"<Game {self.name}>"



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="user")
    profile_pic = db.Column(db.String(200), default="images/pfp.png")  # path in static

    clicked = db.Column(JSON, default=list)  # store game IDs
    played = db.Column(JSON, default=list)
    ratings = db.Column(PickleType, default=dict)

    playlists = db.relationship("ToPlayList", backref="user", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>, Role {self.role}   "
