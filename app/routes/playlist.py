from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user
from app import db
from app.models import ToPlayList, Game, playlist_games
from app.recommender import optimize_play_order, get_game_detail
from app.utils import get_cached_order, set_cached_order
from app.utils import _CACHE


bp = Blueprint("playlist", __name__, url_prefix="/playlist")


@bp.route("/playlist/<int:playlist_id>/reorder", methods=["POST"])
@login_required
def reorder_playlist(playlist_id):
    playlist = ToPlayList.query.get_or_404(playlist_id)
    if playlist.user_id != current_user.id:
        abort(403)

    new_order = request.json.get("order", [])
    if not new_order:
        return {"status": "error"}, 400

    # Save positions in DB
    for idx, game_id in enumerate(new_order):
        db.session.execute(
            playlist_games.update()
            .where(
                (playlist_games.c.playlist_id == playlist_id) &
                (playlist_games.c.game_id == int(game_id))
            )
            .values(position=idx)
        )
    db.session.commit()

    # Update cache
    set_cached_order(playlist.id, [int(gid) for gid in new_order], "custom", [int(gid) for gid in new_order])
    return {"status": "success"}


@bp.route("/<int:playlist_id>/arrange")
@login_required
def arrange_playlist(playlist_id):
    order_type = request.args.get("order_type")
    if order_type:
        session["playlist_order"] = order_type  # save user selection
    return redirect(url_for("playlist.view", playlist_id=playlist_id))



@bp.route("/playlist/<int:playlist_id>")
@login_required
def view(playlist_id):
    playlist = ToPlayList.query.filter_by(id=playlist_id, user_id=current_user.id).first_or_404()
    if playlist.user_id != current_user.id:
        abort(403)

    game_ids = [g.id for g in playlist.games]
    order = session.get("playlist_order", "alpha")  # default to alpha

    # If custom, check cache first, then DB
    if order == "custom":
        cached = get_cached_order(playlist.id, game_ids, order)
        if cached:
            ordered_ids = cached
        else:
            # Fetch positions from DB
            rows = db.session.query(playlist_games.c.game_id)\
                .filter(playlist_games.c.playlist_id == playlist.id)\
                .order_by(playlist_games.c.position.asc()).all()
            db_order = [row[0] for row in rows]

            if set(db_order) == set(game_ids):  # DB custom order exists and valid
                ordered_ids = db_order
                set_cached_order(playlist.id, game_ids, order, ordered_ids)
            else:
                # No valid custom order yet; show current playlist order
                ordered_ids = game_ids
    else:
        # Predefined orders
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


@bp.route("/remove/<int:playlist_id>/<int:game_id>", methods=["POST"])
@login_required
def remove_game(playlist_id, game_id):
    playlist = ToPlayList.query.get_or_404(playlist_id)
    game = Game.query.get_or_404(game_id)

    # Security check: Ensure the user owns the playlist
    if playlist.user_id != current_user.id:
        abort(403)

    # Remove the game from the playlist
    if game in playlist.games:
        playlist.games.remove(game)
        db.session.commit()
        # Invalidate the cache for this playlist since its contents have changed
        invalidate_playlist_cache(playlist_id)
        flash(f"'{game.name}' removed from playlist.", "info")

    # Redirect back to the playlist view
    return redirect(url_for("playlist.view", playlist_id=playlist_id))

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
