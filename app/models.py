from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.types import PickleType

# app/models.py

from app import db
from flask_login import UserMixin

playlist_games = db.Table(
    "playlist_games",
    db.Column("playlist_id", db.Integer, db.ForeignKey("to_play_list.id"), primary_key=True),
    db.Column("game_id", db.Integer, db.ForeignKey("game.id"), primary_key=True)
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


# class ToPlayList(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(120), nullable=False)
#     user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
#
#     games = db.relationship(
#         "Game",
#         secondary=playlist_games,
#         backref="playlists",
#         lazy="dynamic"
#     )

class Game(db.Model):
    """Store minimal metadata for added games so we don’t lose them."""
    id = db.Column(db.Integer, primary_key=True)  # RAWG ID
    name = db.Column(db.String(200))
    image = db.Column(db.String(300))


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
