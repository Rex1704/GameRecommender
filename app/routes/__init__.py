from app.routes import auth, main, admin, playlist

def register_blueprints(app):
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(playlist.bp)
