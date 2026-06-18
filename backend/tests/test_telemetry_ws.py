"""Tests for WebSocket telemetry gateway auth and session management (AEGIS-48).

Acceptance criteria verified:
  1. Invalid JWT closes the WebSocket with close code 4401.
  2. Student not enrolled closes with close code 4403.
  3. Enrolled student connects and is registered in the in-memory dict.
  4. Registry is cleaned up on disconnect; ws_disconnected_at is stamped.
  5. Reconnecting with the same token is accepted and resumes the session.
  6. System handles 200 concurrent connections (load test).
"""

import threading
import time
import uuid
from contextlib import contextmanager
from unittest import mock

import pytest
from jose import jwt
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.routers import telemetry

EXAM_ID = str(uuid.uuid4())
STUDENT_ID = "ws-test-student-001"


def _make_token(user_id: str = STUDENT_ID) -> str:
    return jwt.encode(
        {"sub": user_id}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


@contextmanager
def _ws_client():
    """Return a TestClient with server exceptions propagated quietly."""
    yield TestClient(app, raise_server_exceptions=False)


@contextmanager
def _enrolled_ws(exam_id: str = EXAM_ID, student_id: str = STUDENT_ID):
    """Open a WebSocket connection as a mocked-enrolled student."""
    token = _make_token(student_id)
    with _ws_client() as client:
        with (
            mock.patch("app.routers.telemetry._is_enrolled", return_value=True),
            mock.patch("app.routers.telemetry._mark_disconnected"),
        ):
            with client.websocket_connect(f"/ws/exam/{exam_id}?token={token}") as ws:
                yield ws


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset the connection registry between tests."""
    telemetry._connections.clear()
    yield
    telemetry._connections.clear()


# ---------------------------------------------------------------------------
# 1. Invalid JWT → close code 4401
# ---------------------------------------------------------------------------


def test_invalid_token_closes_with_4401():
    with _ws_client() as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/ws/exam/{EXAM_ID}?token=not.a.valid.jwt"
            ) as ws:
                ws.receive_text()
    assert exc_info.value.code == 4401


def test_expired_token_closes_with_4401():
    """An expired JWT should be treated the same as invalid."""
    from datetime import datetime, timezone

    expired_token = jwt.encode(
        {
            "sub": STUDENT_ID,
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with _ws_client() as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                f"/ws/exam/{EXAM_ID}?token={expired_token}"
            ) as ws:
                ws.receive_text()
    assert exc_info.value.code == 4401


# ---------------------------------------------------------------------------
# 2. Not enrolled → close code 4403
# ---------------------------------------------------------------------------


def test_not_enrolled_closes_with_4403():
    token = _make_token()
    with _ws_client() as client:
        with (
            mock.patch("app.routers.telemetry._is_enrolled", return_value=False),
            pytest.raises(WebSocketDisconnect) as exc_info,
        ):
            with client.websocket_connect(
                f"/ws/exam/{EXAM_ID}?token={token}"
            ) as ws:
                ws.receive_text()
    assert exc_info.value.code == 4403


# ---------------------------------------------------------------------------
# 3. Enrolled student connects and is registered
# ---------------------------------------------------------------------------


def test_enrolled_student_is_registered():
    with _enrolled_ws():
        bucket = telemetry._connections.get(EXAM_ID, {})
        assert STUDENT_ID in bucket, "Connection should be registered while socket is open"


# ---------------------------------------------------------------------------
# 4. Registry is cleaned up on disconnect
# ---------------------------------------------------------------------------


def test_registry_cleared_after_disconnect():
    with _enrolled_ws():
        pass  # context exit triggers disconnect + cleanup
    bucket = telemetry._connections.get(EXAM_ID, {})
    assert STUDENT_ID not in bucket, "Registry entry should be removed after disconnect"


def test_mark_disconnected_called_on_close():
    token = _make_token()
    with _ws_client() as client:
        with (
            mock.patch("app.routers.telemetry._is_enrolled", return_value=True),
            mock.patch("app.routers.telemetry._mark_disconnected") as mock_stamp,
        ):
            with client.websocket_connect(
                f"/ws/exam/{EXAM_ID}?token={token}"
            ):
                pass  # immediate close
    mock_stamp.assert_called_once()
    call_kwargs = mock_stamp.call_args
    assert call_kwargs[0][1] == STUDENT_ID  # second positional arg is student_id


# ---------------------------------------------------------------------------
# 5. Reconnection with same token is accepted
# ---------------------------------------------------------------------------


def test_reconnect_with_same_token_accepted():
    # First connection
    with _enrolled_ws():
        pass
    # Second connection — same student, same exam
    with _enrolled_ws():
        bucket = telemetry._connections.get(EXAM_ID, {})
        assert STUDENT_ID in bucket, "Reconnection with same JWT should be accepted"


def test_reconnect_replaces_stale_registry_entry():
    """Later connection's WebSocket object should be in the registry."""
    first_socket_ref = []

    with _enrolled_ws():
        first_socket_ref.append(telemetry._connections.get(EXAM_ID, {}).get(STUDENT_ID))

    with _enrolled_ws():
        current = telemetry._connections.get(EXAM_ID, {}).get(STUDENT_ID)
        # The first socket is closed; registry holds the current (second) socket
        assert current is not None
        assert current is not first_socket_ref[0], (
            "Registry should hold the new socket, not the stale first one"
        )


# ---------------------------------------------------------------------------
# 6. Load: 200 concurrent connections
# ---------------------------------------------------------------------------


def _connect_and_hold(student_id: str, results: dict, idx: int) -> None:
    """Open a WS connection, hold it briefly, then close. Record success."""
    token = _make_token(student_id)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with (
            mock.patch("app.routers.telemetry._is_enrolled", return_value=True),
            mock.patch("app.routers.telemetry._mark_disconnected"),
        ):
            with client.websocket_connect(
                f"/ws/exam/{EXAM_ID}?token={token}"
            ):
                time.sleep(0.02)  # hold open briefly
        results[idx] = True
    except Exception as exc:
        results[idx] = str(exc)


def test_200_concurrent_connections():
    n = 200
    student_ids = [f"ws-load-{i:04d}" for i in range(n)]
    results: dict[int, object] = {}

    threads = [
        threading.Thread(
            target=_connect_and_hold,
            args=(sid, results, i),
            daemon=True,
        )
        for i, sid in enumerate(student_ids)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    successes = sum(1 for v in results.values() if v is True)
    failed_indices = [i for i, v in results.items() if v is not True]

    assert successes == n, (
        f"Only {successes}/{n} connections succeeded. "
        f"First failures: {[results[i] for i in failed_indices[:3]]}"
    )
