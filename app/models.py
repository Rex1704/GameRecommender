from app.extensions import db
from flask_login import UserMixin
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.types import PickleType

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

    def __repr__(self):
        return f"<User {self.username}>, Role {self.role}   "
