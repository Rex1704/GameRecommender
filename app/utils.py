from functools import wraps, lru_cache
from flask import abort
from flask_login import current_user
import hashlib
from urllib.parse import quote

def _hash_playlist(playlist_id: int, game_ids: list[int], order_type: str) -> str:
    """Return a stable key from playlist id + its games + order type."""
    raw = f"{playlist_id}:{sorted(game_ids)}:{order_type}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# Simple in-memory cache (per process)
_CACHE = {}

def get_cached_order(playlist_id: int, game_ids: list[int], order_type: str):
    key = _hash_playlist(playlist_id, game_ids, order_type)
    return _CACHE.get(key)

def set_cached_order(playlist_id: int, game_ids: list[int], order_type: str, order: list[int]):
    key = _hash_playlist(playlist_id, game_ids, order_type)
    _CACHE[key] = order


# custom Placeholder fetched from placehold.co
def first_cap(value: str, fallback: str = "?") -> str:
    if not value or not isinstance(value, str) or not value.strip():
        return fallback
    return value.strip()[0].upper()

def _hsl_to_rgb(h, s, l):
    # h in [0,360), s,l in [0,1]
    c = (1 - abs(2*l - 1)) * s
    x = c * (1 - abs((h/60) % 2 - 1))
    m = l - c/2
    if   0 <= h < 60:  r,g,b = c, x, 0
    elif 60 <= h <120: r,g,b = x, c, 0
    elif 120<= h<180:  r,g,b = 0, c, x
    elif 180<= h<240:  r,g,b = 0, x, c
    elif 240<= h<300:  r,g,b = x, 0, c
    else:              r,g,b = c, 0, x
    to255 = lambda v: int(round((v + m) * 255))
    return to255(r), to255(g), to255(b)

def _rgb_to_hex(r,g,b):  # -> "RRGGBB"
    return f"{r:02X}{g:02X}{b:02X}"

def _hash_hue(s: str) -> int:
    h = hashlib.md5((s or "").encode("utf-8")).hexdigest()
    return int(h[:6], 16) % 360

def two_shades_hex(name: str):
    """
    Deterministic hue from name; return (bg_hex, fg_hex) as two shades of same hue.
    bg: slightly darker, fg: very light for contrast.
    """
    h = _hash_hue(name or "placeholder")
    # tune these for taste/contrast
    bg = _rgb_to_hex(*_hsl_to_rgb(h, 0.55, 0.30))  # darker
    fg = _rgb_to_hex(*_hsl_to_rgb(h, 0.70, 0.90))  # lighter
    return bg, fg


def placeholder_url(name: str, w: int = 300, h: int = 400, text: str | None = None) -> str:
    bg, fg = two_shades_hex(name)
    label = text if text is not None else first_cap(name)
    # Force PNG (placehold.co/<WxH>/<bg>/<fg>.png?text=...)
    return f"https://placehold.co/{w}x{h}/{bg}/{fg}.png?text={quote(label)}"

# role required for some pages like admin which requires admin privilige
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
