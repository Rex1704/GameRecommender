from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from app import db
from app.models import ToPlayList, Game
from app.recommender import optimize_play_order, get_game_detail
from app.utils import get_cached_order, set_cached_order
from app.utils import _CACHE



bp = Blueprint("playlist", __name__, url_prefix="/playlist")

@bp.route("/playlist/<int:playlist_id>/arrange", methods=["POST"])
@login_required
def arrange_playlist(playlist_id):
    order_type = request.form.get("order_type")
    session["playlist_order"] = order_type  # save choice in cookie

    return redirect(url_for("playlist.view", playlist_id=playlist_id))


@bp.route("/playlist/<int:playlist_id>")
@login_required
def view(playlist_id):
    playlist = ToPlayList.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()

    if playlist.user_id != current_user.id:
        abort(403)

    game_ids = [g.id for g in playlist.games]
    order = session.get("playlist_order")
    cached = get_cached_order(playlist.id, game_ids, order)

    if cached:
        ordered_ids = cached
    else:
        if order == "alpha":
            ordered_ids = sorted(game_ids, key=lambda g: get_game_detail(g)['name'].lower())
        elif order == "release":
            ordered_ids = sorted(game_ids, key=lambda g: get_game_detail(g)['released'] or "9999-12-31")
        elif order == "playtime":
            ordered_ids = sorted(game_ids, key=lambda g: get_game_detail(g)['playtime'] or 0)
        elif order == "special":
            ordered_ids = optimize_play_order(game_ids)
        else:
            ordered_ids = game_ids

        set_cached_order(playlist.id, game_ids, order, ordered_ids)

    ordered_games = [get_game_detail(gid) for gid in ordered_ids]

    return render_template("playlist.html", playlist=playlist, games=ordered_games, order=order)

@bp.route("/create", methods=["POST"])
@login_required
def create_playlist():
    name = request.form.get("name")
    if not name:
        flash("Playlist name is required.", "danger")
        return redirect(url_for("auth.profile", section="playlist"))

    # Check if this user already has a playlist with that name
    existing = ToPlayList.query.filter_by(user_id=current_user.id, name=name).first()
    if existing:
        flash("You already have a playlist with that name.", "warning")
        return redirect(url_for("auth.profile", section="playlist"))

    new_list = ToPlayList(name=name, user_id=current_user.id)
    db.session.add(new_list)
    db.session.commit()

    flash("Playlist created successfully!", "success")
    return redirect(url_for("auth.profile", section="playlist"))

@bp.route("/delete/<int:playlist_id>", methods=["POST"])
@login_required
def delete(playlist_id):
    playlist = ToPlayList.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        flash("Not authorized!", "danger")
        return redirect(url_for("main.feed"))
    db.session.delete(playlist)
    db.session.commit()
    flash("Playlist deleted.", "info")
    return redirect(url_for("auth.profile", section="playlist"))

def invalidate_playlist_cache(playlist_id):
    keys_to_delete = [k for k in _CACHE if k.startswith(str(playlist_id))]
    for k in keys_to_delete:
        _CACHE.pop(k, None)

@bp.route("/add/<int:game_id>", methods=["POST"])
@login_required
def add_game(game_id):
    game_name = request.form.get("name")
    game_img = request.form.get("image")
    game = Game.query.get(game_id)
    if not game:
        game = Game(id=game_id, name=game_name, image=game_img)
        db.session.add(game)
    # Existing playlists selected
    selected_ids = request.form.getlist("playlists")
    for pid in selected_ids:
        pl = ToPlayList.query.filter_by(id=pid, user_id=current_user.id).first()
        if pl and game not in pl.games:
            pl.games.append(game)
        # invalidate_playlist_cache(pid)

    # New playlist creation
    new_name = request.form.get("new_name", "").strip()
    if new_name:
        # check if playlist with this name already exists
        existing = ToPlayList.query.filter_by(user_id=current_user.id, name=new_name).first()
        if not existing:
            new_pl = ToPlayList(name=new_name, user_id=current_user.id)
            new_pl.games.append(game)  # add game to new playlist
            db.session.add(new_pl)
        else:
            # if playlist already exists, just add game to it
            if game not in existing.games:
                existing.games.append(game)

    db.session.commit()

    # redirect back to the game page
    return redirect(request.referrer or url_for("auth.profile", section="playlist"))
