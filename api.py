import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from datetime import timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select

from config.settings import settings
from src.database.db import SessionLocal, init_db
from src.database.models import EntityMapping, IngestionRun, Record
from src.integrations.export import CATEGORIES, csv_for, export_to_sheets
from src.pipeline.ingestion_pipeline import COLLECTORS, run_collector
from src.resolver.entity_resolver import EntityResolver

SESSION_COOKIE = "graphone_admin"
SESSION_MAX_AGE = 8 * 60 * 60
PUBLIC_DIR = Path(__file__).resolve().parent / "public"


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


def _admin_enabled(password: str | None = None, session_secret: str | None = None) -> bool:
    configured_password = settings.dashboard_password if password is None else password
    configured_secret = settings.dashboard_session_secret if session_secret is None else session_secret
    return len(configured_password) >= 12 and len(configured_secret) >= 32


def _session_token(secret: str, issued_at: int | None = None) -> str:
    timestamp = issued_at if issued_at is not None else int(time.time())
    signature = hmac.new(secret.encode(), str(timestamp).encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def _valid_session(token: str | None, secret: str, now: int | None = None) -> bool:
    if not token:
        return False
    try:
        issued_text, supplied_signature = token.split(".", 1)
        issued_at = int(issued_text)
    except (ValueError, TypeError):
        return False
    current_time = now if now is not None else int(time.time())
    if issued_at > current_time + 60 or current_time - issued_at > SESSION_MAX_AGE:
        return False
    expected_signature = _session_token(secret, issued_at).split(".", 1)[1]
    return hmac.compare_digest(supplied_signature, expected_signature)


def require_admin(request: Request) -> None:
    if not _admin_enabled():
        raise HTTPException(
            status_code=503,
            detail="Configure DASHBOARD_PASSWORD (12+ characters) and DASHBOARD_SESSION_SECRET (32+ characters).",
        )
    if not _valid_session(request.cookies.get(SESSION_COOKIE), settings.dashboard_session_secret):
        raise HTTPException(status_code=401, detail="Admin sign-in required.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="GraphOne Intelligence API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "schema_version": "1.0", "admin_enabled": _admin_enabled()}


@app.get("/auth/status")
def auth_status(request: Request) -> dict:
    return {
        "admin_enabled": _admin_enabled(),
        "authenticated": _admin_enabled() and _valid_session(
            request.cookies.get(SESSION_COOKIE), settings.dashboard_session_secret
        ),
    }


@app.post("/auth/login")
def login(body: LoginRequest, request: Request):
    if not _admin_enabled():
        raise HTTPException(
            status_code=503,
            detail="Configure DASHBOARD_PASSWORD (12+ characters) and DASHBOARD_SESSION_SECRET (32+ characters).",
        )
    expected = hashlib.sha256(settings.dashboard_password.encode()).digest()
    supplied = hashlib.sha256(body.password.encode()).digest()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid password.")
    from fastapi.responses import JSONResponse

    response = JSONResponse({"authenticated": True})
    response.set_cookie(
        SESSION_COOKIE,
        _session_token(settings.dashboard_session_secret),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
        samesite="strict",
        path="/",
    )
    return response


@app.post("/auth/logout")
def logout():
    from fastapi.responses import JSONResponse

    response = JSONResponse({"authenticated": False})
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")
    return response


@app.get("/collectors")
def collectors() -> dict:
    return {"collectors": list(COLLECTORS)}


@app.post("/collectors/{name}/run", dependencies=[Depends(require_admin)])
async def run_named_collector(name: str) -> dict:
    if name not in COLLECTORS:
        raise HTTPException(status_code=404, detail=f"Unknown collector: {name}")
    return await run_collector(name)


@app.get("/records")
def records(category: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    if category is not None and category not in COLLECTORS:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    with SessionLocal() as session:
        query = select(Record).order_by(Record.published_at.desc(), Record.first_seen_at.desc()).limit(limit)
        if category:
            query = query.where(Record.category == category)
        items = session.scalars(query)
        return [{
            "category": item.category,
            "title": item.title,
            "organization": item.organization,
            "source": item.source_name,
            "source_url": item.source_url,
            "url": item.record_url,
            "summary": item.summary,
            "published_at": item.published_at.replace(tzinfo=timezone.utc).isoformat()
            if item.published_at and item.published_at.tzinfo is None else
            item.published_at.isoformat() if item.published_at else None,
            "first_seen_at": item.first_seen_at.isoformat(),
            "last_seen_at": item.last_seen_at.isoformat(),
            "extraction_status": item.extraction_status,
        } for item in items]


@app.get("/runs")
def runs(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    with SessionLocal() as session:
        items = session.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit))
        return [{"collector": item.collector, "status": item.status, "records_found": item.records_found,
                 "records_saved": item.records_saved, "error": item.error,
                 "started_at": item.started_at.isoformat(),
                 "finished_at": item.finished_at.isoformat() if item.finished_at else None}
                for item in items]


@app.get("/entities/mappings")
def entity_mappings() -> list[dict]:
    with SessionLocal() as session:
        items = session.scalars(select(EntityMapping).order_by(EntityMapping.created_at.desc()).limit(1000))
        return [{"raw_name": item.raw_name, "canonical_name": item.canonical_name,
                 "confidence": item.confidence, "method": item.method, "source_url": item.source_url,
                 "created_at": item.created_at.isoformat()} for item in items]


@app.get("/entities/resolve")
def resolve_entity(name: str = Query(min_length=1, max_length=300)) -> dict:
    return EntityResolver().resolve(name)


@app.get("/exports/{category}.csv")
def export_csv(category: str):
    if category not in {*CATEGORIES, "entity_mapping"}:
        raise HTTPException(status_code=404, detail="Unknown export category.")
    return StreamingResponse(
        iter([csv_for(category)]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{category}.csv"'},
    )


@app.post("/exports/sheets", dependencies=[Depends(require_admin)])
def export_sheets() -> dict:
    result = export_to_sheets()
    if result.errors:
        raise HTTPException(status_code=502, detail={"uploaded": result.uploaded, "errors": result.errors})
    return {"uploaded": result.uploaded, "skipped": result.skipped, "errors": result.errors}


if PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
