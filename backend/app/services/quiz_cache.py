# backend/app/services/quiz_cache.py
# AEGIS-108: In-process LRU cache for GET /quizzes/{quiz_id} responses.
#
# Quizzes are immutable once state = open (no edits allowed during active
# exams), making them ideal candidates for short-TTL in-process caching.
# This eliminates repeated PostgreSQL reads when many students load the
# same exam shell simultaneously.
#
# Memory impact estimate:
#   maxsize=200 quizzes × ~5KB avg quiz payload (title + 10 questions)
#   ≈ 1MB max memory footprint — negligible for a container with 512MB+.
#
# TTL=300s (5 minutes): short enough that a professor editing a draft quiz
# sees changes reflected quickly; long enough to absorb burst reads at exam
# start when all students load the shell simultaneously.

from threading import Lock

from cachetools import TTLCache

# 200 quizzes max, 5-minute TTL
_cache: TTLCache = TTLCache(maxsize=200, ttl=300)
_lock = Lock()


def get_cached_quiz(quiz_id: str) -> dict | None:
    """Return cached quiz dict or None on cache miss."""
    with _lock:
        return _cache.get(quiz_id)


def set_cached_quiz(quiz_id: str, data: dict) -> None:
    """Store a quiz dict in the cache."""
    with _lock:
        _cache[quiz_id] = data


def invalidate_cached_quiz(quiz_id: str) -> None:
    """Remove a quiz from the cache (call on update or delete)."""
    with _lock:
        _cache.pop(quiz_id, None)


def cache_stats() -> dict:
    """Return current cache size and max size — useful for health checks."""
    with _lock:
        return {"size": len(_cache), "maxsize": _cache.maxsize, "ttl": _cache.ttl}
