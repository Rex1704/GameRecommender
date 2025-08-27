from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, bcrypt
from app.models import User
from app.recommender import get_game_detail
from werkzeug.utils import secure_filename
import os

bp = Blueprint("auth", __name__, url_prefix="/auth")

UPLOAD_FOLDER = os.path.join("..", "static", "images")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS



@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("signup.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("main.feed"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("login.html")

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    section = request.args.get("section", "general")
    played_games = []
    playlists = []

    if section == "played":
        played_ids = current_user.played or []  # make sure played is stored in DB as JSON/array
        played_games = [get_game_detail(pid) for pid in played_ids if get_game_detail(pid)]

    if section == "playlist":
        playlists = current_user.playlists

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        file = request.files.get("profile_pic")

        if username:
            current_user.username = username
        if email:
            current_user.email = email
        if password:
            current_user.password = bcrypt.generate_password_hash(password).decode("utf-8")
        if file and allowed_file(file.filename):
            filename = secure_filename(f"user_{current_user.id}_" + file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            current_user.profile_pic = filepath

        db.session.commit()
        flash("Profile updated!", "success")
        return redirect(url_for("auth.profile"))

    return render_template("profile.html", user=current_user, section=section,played_games=played_games, playlists=playlists)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.feed"))
