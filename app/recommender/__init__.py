# app/recommender/__init__.py
from .recommender import (
    hybrid_recommend,
    recommend_similar_games,
    get_diverse_feed,
    get_game_detail,
    extract_franchise_key
)

from .playlist import (
    optimize_play_order,
)

__all__ = [
    "hybrid_recommend",
    "recommend_similar_games",
    "get_diverse_feed",
    "get_game_detail",
    "extract_franchise_key",
    "optimize_play_order",
]
