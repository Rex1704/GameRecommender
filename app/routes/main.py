from flask import Blueprint, render_template, request, redirect, url_for, session, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.recommender import (
    get_diverse_feed, hybrid_recommend, recommend_similar_games, get_game_detail
)
import json

bp = Blueprint("main", __name__)

def set_rating(game_id: int, rating: int):
    """Set or update a rating for the current user."""
    ratings = dict(_get_user_list("ratings"))
    ratings[str(game_id)] = rating
    setattr(current_user, "ratings", ratings)
    db.session.commit()

def get_rating(game_id: int) -> int:
    """Get rating if exists, else None."""
    ratings = dict(_get_user_list("ratings"))
    rating = None
    try:
        rating = ratings[str(game_id)]
    finally:
        return rating

def _get_cookie_list(key):
    raw = request.cookies.get(key)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []

def _set_cookie_list(resp, key, value_list):
    resp.set_cookie(key, json.dumps(value_list), max_age=60*60*24*7)  # 7 days
    return resp

def _get_user_list(key):
    if not current_user.is_authenticated:
        return []
    return getattr(current_user, key) or []

def _push_user_unique(key, value):
    if not current_user.is_authenticated:
        return
    arr = set(getattr(current_user, key) or [])
    arr.add(value)
    setattr(current_user, key, list(arr))
    db.session.commit()

def _pop_user_unique(key, value):
    if not current_user.is_authenticated:
        return
    arr = set(getattr(current_user, key) or [])
    arr.remove(value)
    setattr(current_user, key, list(arr))
    db.session.commit()


@bp.route("/")
def index():
    # keep your onboarding if you have it; otherwise go straight to feed
    return redirect(url_for("main.feed"))

@bp.route("/feed")
def feed():
    if current_user.is_authenticated:
        clicked = _get_user_list("clicked")
        played = _get_user_list("played")
        ratings = _get_user_list("ratings")
    else:
        clicked = _get_cookie_list("clicked")
        played = _get_cookie_list("played")
        ratings = _get_cookie_list("ratings")

    if clicked or played:
        recs = hybrid_recommend(clicked_ids=clicked, played_ids=played, user_ratings=ratings, n=40)
    else:
        # fallback → diverse popular feed across genres
        recs = get_diverse_feed(40)

    played_list = set(played)
    return render_template("feed.html", recommendations=recs, played_list=played_list)


@bp.route("/game/<int:game_id>")
def game_detail(game_id):
    game = get_game_detail(game_id)
    similar = recommend_similar_games(game_id=game_id, n=12)
    if not game:
        return redirect(url_for("main.feed"))

    if current_user.is_authenticated:
        _push_user_unique("clicked", game_id)
        played_list = _get_user_list("played")
        ratings=_get_user_list("ratings")
        is_played = game_id in played_list
    else:
        clicked = set(_get_cookie_list("clicked"))
        clicked.add(game_id)
        resp = make_response(render_template("game.html", game=game, recommendations=similar))
        return _set_cookie_list(resp, "clicked", list(clicked))

    current_rating = get_rating(game_id)

    return render_template("game.html", game=game, recommendations=similar,
                           current_rating=current_rating, is_played=is_played)


@bp.route("/mark_played/<int:game_id>", methods=["POST"])
@login_required
def mark_played(game_id):
    played = set(_get_user_list("played"))
    if game_id in played:
        _pop_user_unique("played", game_id)
    else:
        # toggle ON → add to played
        _push_user_unique("played", game_id)
        # optional: remove from clicked so it doesn’t affect recs
        clicked = set(_get_user_list("clicked"))
        if game_id in clicked:
            clicked.remove(game_id)
            session["clicked"] = list(clicked)

    # _push_user_unique("played", played)
    session["played"] = list(played)

    return redirect(request.referrer or url_for("auth.login"))


@bp.route("/rate/<int:game_id>/<int:rating>", methods=["POST"])
@login_required
def rate_game(game_id, rating):
    if not (1 <= rating <= 5):
        return redirect(request.referrer or url_for("main.feed"))

    set_rating(game_id, rating)
    return redirect(request.referrer or url_for("main.game_detail", game_id=game_id))


@bp.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("main.feed"))
