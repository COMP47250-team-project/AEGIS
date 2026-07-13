# backend/tests/test_quiz_cache.py
# AEGIS-108: Unit tests for the in-process LRU quiz cache.
#
# Tests use only the cache module directly — no DB, no FastAPI app needed.
# TTL expiry is tested by replacing the internal cache with a 1-second TTL
# instance so the test doesn't have to wait 5 minutes.

import time
from unittest.mock import patch

import pytest
from cachetools import TTLCache

import app.services.quiz_cache as quiz_cache_module
from app.services.quiz_cache import (
    get_cached_quiz,
    invalidate_cached_quiz,
    set_cached_quiz,
    cache_stats,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset the cache before every test so tests don't bleed into each other."""
    quiz_cache_module._cache.clear()
    yield
    quiz_cache_module._cache.clear()


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------

def test_cache_miss_returns_none():
    result = get_cached_quiz("nonexistent-id")
    assert result is None


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

def test_cache_hit_returns_stored_data():
    quiz_data = {"id": "quiz-1", "title": "Test Quiz", "questions": []}
    set_cached_quiz("quiz-1", quiz_data)

    result = get_cached_quiz("quiz-1")
    assert result is not None
    assert result["title"] == "Test Quiz"
    assert result["questions"] == []


def test_cache_hit_same_object():
    quiz_data = {"id": "quiz-2", "title": "Another Quiz"}
    set_cached_quiz("quiz-2", quiz_data)

    # Should return the exact same object (no copy)
    result = get_cached_quiz("quiz-2")
    assert result is quiz_data


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

def test_invalidation_removes_entry():
    set_cached_quiz("quiz-3", {"id": "quiz-3", "title": "To Be Removed"})
    assert get_cached_quiz("quiz-3") is not None

    invalidate_cached_quiz("quiz-3")
    assert get_cached_quiz("quiz-3") is None


def test_invalidation_of_nonexistent_key_does_not_raise():
    # Should silently do nothing, not raise KeyError
    invalidate_cached_quiz("does-not-exist")


def test_invalidation_only_removes_target_key():
    set_cached_quiz("quiz-a", {"id": "quiz-a"})
    set_cached_quiz("quiz-b", {"id": "quiz-b"})

    invalidate_cached_quiz("quiz-a")

    assert get_cached_quiz("quiz-a") is None
    assert get_cached_quiz("quiz-b") is not None


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

def test_cache_expires_after_ttl():
    # Replace the module-level cache with a 1-second TTL for this test
    short_ttl_cache = TTLCache(maxsize=200, ttl=1)
    with patch.object(quiz_cache_module, "_cache", short_ttl_cache):
        set_cached_quiz("quiz-ttl", {"id": "quiz-ttl", "title": "Expiring Quiz"})
        assert get_cached_quiz("quiz-ttl") is not None

        # Wait for TTL to expire
        time.sleep(1.1)
        assert get_cached_quiz("quiz-ttl") is None


# ---------------------------------------------------------------------------
# Multiple entries
# ---------------------------------------------------------------------------

def test_multiple_entries_independent():
    set_cached_quiz("q1", {"id": "q1", "title": "Quiz 1"})
    set_cached_quiz("q2", {"id": "q2", "title": "Quiz 2"})
    set_cached_quiz("q3", {"id": "q3", "title": "Quiz 3"})

    assert get_cached_quiz("q1")["title"] == "Quiz 1"
    assert get_cached_quiz("q2")["title"] == "Quiz 2"
    assert get_cached_quiz("q3")["title"] == "Quiz 3"


# ---------------------------------------------------------------------------
# Cache stats
# ---------------------------------------------------------------------------

def test_cache_stats_reflects_current_size():
    stats_before = cache_stats()
    assert stats_before["size"] == 0

    set_cached_quiz("quiz-stats", {"id": "quiz-stats"})
    stats_after = cache_stats()
    assert stats_after["size"] == 1
    assert stats_after["maxsize"] == 200
    assert stats_after["ttl"] == 300
