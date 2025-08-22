from flask import Blueprint, render_template, redirect, url_for, session, request
from flask_login import login_required
from app.recommender.recommender import (
    get_diverse_feed,
    recommend_from_profile,
    recommend_from_genres,
    get_game_detail
)

bp = Blueprint("main", __name__)

@bp.route("/", methods=["GET", "POST"])
def index():
    if session.get("onboarded", False):
        return redirect(url_for("main.feed"))

    if request.method == "POST":
        chosen_genres = request.form.getlist("genres")
        session["genres"] = chosen_genres
        session["clicked"] = []
        session["onboarded"] = True
        return redirect(url_for("main.feed"))

    from app.recommender.recommender import df
    genres = sorted(set(g for sub in df["genres"].dropna().str.split(", ") for g in sub))
    return render_template("index.html", genres=genres)

@bp.route("/feed")
@login_required
def feed():
    chosen_genres = session.get("genres", [])
    clicked_games = session.get("clicked", [])

    if clicked_games:
        recs = recommend_from_profile(clicked_games, n=54)
    elif chosen_genres:
        recs = recommend_from_genres(chosen_genres, n=54)
    else:
        recs = get_diverse_feed(n=54)

    return render_template("feed.html", recommendations=recs)

@bp.route("/game/<int:game_id>")
@login_required
def game_detail(game_id):
    game = get_game_detail(game_id)
    similar = recommend_from_profile([game_id], n=12)

    clicked = session.get("clicked", [])
    if game_id not in clicked:
        clicked.append(game_id)
        session["clicked"] = clicked

    return render_template("game.html", game=game, recommendations=similar)

@bp.route("/reset")
@login_required
def reset():
    session.clear()
    return redirect(url_for("main.index"))
