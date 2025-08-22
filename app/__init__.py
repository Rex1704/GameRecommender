from flask import Flask
from app.extensions import db, bcrypt, login_manager
from app.models import User
from app.routes import register_blueprints
import os
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), "templates"),
                static_folder=os.path.join(os.path.dirname(__file__), "static"))
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URI", "sqlite:///site.db")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecret")
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    register_blueprints(app)
    return app
