from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.utils import role_required
from app.extensions import db
from app.models import User

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    users = User.query.all()
    return render_template("admin/dashboard.html", users=users)

@bp.route("/set_role/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def set_role(user_id):
    role = request.form.get("role")
    user = User.query.get_or_404(user_id)
    user.role = role
    db.session.commit()
    flash(f"Updated {user.username}'s role to {role}", "success")
    return redirect(url_for("admin.dashboard"))

@bp.route("/delete/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted user {user.username}", "danger")
    return redirect(url_for("admin.dashboard"))
