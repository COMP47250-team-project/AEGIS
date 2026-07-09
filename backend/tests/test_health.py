"""Tests for the /api/health endpoint (AEGIS-89)."""

import pytest
from httpx import AsyncClient

import app.routers.health as health_module


@pytest.mark.asyncio
async def test_health_ok_in_local_config(client: AsyncClient) -> None:
    """Local/Docker Compose config: db ok, service_bus + blob disabled."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["service_bus"] == "disabled"
    assert body["blob"] == "disabled"
    assert body["version"]  # non-empty (pyproject version or APP_VERSION)


@pytest.mark.asyncio
async def test_healthz_alias_still_works(client: AsyncClient) -> None:
    """The legacy /healthz path maps to the same handler."""
    res = await client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_db_error_returns_503_and_error_status(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fail(_session: object) -> str:
        return "error"

    monkeypatch.setattr(health_module, "_check_db", _fail)
    res = await client.get("/api/health")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "error"
    assert body["db"] == "error"


@pytest.mark.asyncio
async def test_service_bus_error_is_degraded_not_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _sb_error() -> str:
        return "error"

    monkeypatch.setattr(health_module, "_check_service_bus", _sb_error)
    res = await client.get("/api/health")
    assert res.status_code == 200  # db is ok, so not 503
    assert res.json()["status"] == "degraded"


def test_version_prefers_app_version_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "1.2.3")
    assert health_module._version() == "1.2.3"


def test_version_falls_back_to_pyproject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_VERSION", raising=False)
    # Falls back to the [project].version field in backend/pyproject.toml.
    assert health_module._version() == "0.1.0"
