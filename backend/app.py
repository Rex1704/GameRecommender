from flask import Flask, render_template, request, redirect, url_for, session
import pickle
import numpy as np
import pandas as pd
import os

# Load model
with open("model.pkl", "rb") as f:
    df, vectorizer, scaler, svd, normalizer, kmeans, similarity = pickle.load(f)

app = Flask(__name__, template_folder=os.path.join('..', 'templates'),
            static_folder=os.path.join('..', 'static'))
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = "supersecretkey"

# ---- Utility ----
def get_diverse_feed(n=50):
    return df.sample(n).to_dict(orient="records")

def recommend_from_profile(clicked_ids, n=50):
    # Average similarity of all clicked games
    indices = [df[df["id"] == cid].index[0] for cid in clicked_ids if cid in df["id"].values]
    if not indices:
        return get_diverse_feed(n)

    avg_sim = np.mean(similarity[indices], axis=0)
    sim_scores = sorted(list(enumerate(avg_sim)), key=lambda x: x[1], reverse=True)

    rec_indices = [i for i, _ in sim_scores if df.iloc[i]["id"] not in clicked_ids][:n]
    return df.iloc[rec_indices].to_dict(orient="records")

def recommend_from_genres(genres, n=50):
    mask = df["genres"].apply(lambda g: any(gen in g for gen in genres))
    if mask.sum() == 0:
        return get_diverse_feed(n)
    return df[mask].sample(min(n, mask.sum())).to_dict(orient="records")

# ---- Routes ----
@app.route("/", methods=["GET", "POST"])
def index():
    # If not first time, skip to feed
    if session.get("onboarded", False):
        return redirect(url_for("feed"))

    if request.method == "POST":
        chosen_genres = request.form.getlist("genres")
        session["genres"] = chosen_genres
        session["clicked"] = []
        session["onboarded"] = True
        return redirect(url_for("feed"))

    genres = sorted(set(g for sub in df["genres"].dropna().str.split(", ") for g in sub))
    return render_template("index.html", genres=genres)

@app.route("/feed")
def feed():
    chosen_genres = session.get("genres", [])
    clicked_games = session.get("clicked", [])

    if clicked_games:
        recs = recommend_from_profile(clicked_games, n=50)
    elif chosen_genres:
        recs = recommend_from_genres(chosen_genres, n=50)
    else:
        recs = get_diverse_feed(n=50)

    return render_template("feed.html", recommendations=recs)

details_df = pd.read_csv("game_details.csv")

@app.route("/game/<int:game_id>")
def game_detail(game_id):
    game = df[df["id"] == game_id].iloc[0].to_dict()
    similar = recommend_from_profile([game_id], n=12)

    # Update user profile
    clicked = session.get("clicked", [])
    if game_id not in clicked:
        clicked.append(game_id)
        session["clicked"] = clicked

    details = details_df[details_df["name"] == game["name"]].to_dict(orient="records")
    if details:
        game.update(details[0])  # merge details into same dict

    return render_template("game.html", game=game, recommendations=similar)

@app.route("/reset")
def reset():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
