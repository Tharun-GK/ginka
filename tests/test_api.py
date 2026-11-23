import asyncio

import pytest
from fastapi import HTTPException

import api
from src.database.db import init_db


def test_health_and_collector_routes():
    init_db()
    assert api.health()["status"] == "ok"
    assert "research" in api.collectors()["collectors"]
    with pytest.raises(HTTPException) as category_error:
        api.records(category="untrusted", limit=20)
    assert category_error.value.status_code == 400
    with pytest.raises(HTTPException) as collector_error:
        asyncio.run(api.run_named_collector("untrusted"))
    assert collector_error.value.status_code == 404


def test_admin_dependency_rejects_missing_session(monkeypatch):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/collectors/research/run",
        "raw_path": b"/collectors/research/run",
        "query_string": b"",
        "headers": [],
        "server": ("example.com", 443),
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)
    monkeypatch.setattr(api, "_admin_enabled", lambda: True)
    with pytest.raises(HTTPException) as error:
        api.require_admin(request)
    assert error.value.status_code == 401


def test_sqlite_is_rejected_for_vercel_runtime(monkeypatch):
    from src.database import db

    monkeypatch.setattr(db, "IS_VERCEL", True)
    with pytest.raises(RuntimeError, match="persistent PostgreSQL"):
        db.init_db()
