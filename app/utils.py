from functools import wraps
from flask import abort
from flask_login import current_user

def role_required(role):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)  # unauthorized
            if current_user.role != role:
                return abort(403)  # forbidden
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
