from app import create_app, db
from app.models import User, Game
from app.extensions import bcrypt
from scripts.seed_games import seed_games
import os

def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        # Seed games
        if not Game.query.first():
            seed_games()

        # Seed admin
        if not User.query.filter_by(role="admin").first():
            admin_mail = os.getenv("ADMIN_EMAIL", "admin@example.com")
            admin_passwd = os.getenv("ADMIN_PASSWD", "admin123")
            hashed_pw = bcrypt.generate_password_hash(admin_passwd).decode("utf-8")
            admin = User(username="admin", email=admin_mail, password=hashed_pw, role="admin")
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created")

if __name__ == "__main__":
    seed()
