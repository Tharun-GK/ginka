from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import EntityMapping, IngestionRun, Job, News, Product, Record, ResearchPaper, Startup

SCHEMA_VERSION = "1.0"
RECORD_MODELS = {"startup": Startup, "product": Product, "research": ResearchPaper,
                 "job": Job, "news": News}


def fingerprint(category: str, url: str, title: str) -> str:
    identity = url.strip() or title.strip().casefold()
    return hashlib.sha256(f"{category}:{identity}".encode("utf-8")).hexdigest()


def upsert_records(session: Session, records: list[dict[str, Any]]) -> int:
    saved = 0
    now = datetime.now(timezone.utc)
    for item in records:
        record_url = item["url"]
        parsed = urlparse(record_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Record URL must be an absolute HTTP(S) URL: {record_url!r}")
        source_url = item.get("source_url") or record_url
        key = fingerprint(item["category"], record_url, item["title"])
        existing = session.scalar(
            select(Record).where(Record.category == item["category"], Record.fingerprint == key)
        )
        values = {
            "organization": item.get("organization", "") or "",
            "source_name": item["source_name"],
            "source_url": source_url,
            "record_url": record_url,
            "summary": item.get("summary", "") or "",
            "raw_data": (
                item["raw_data"] if isinstance(item.get("raw_data"), str)
                else json.dumps(item.get("raw_data", item), ensure_ascii=False, default=str)
            ),
            "published_at": item.get("published_at"),
            "first_seen_at": item.get("first_seen_at", now),
            "last_seen_at": now,
        }
        if existing:
            for name, value in values.items():
                setattr(existing, name, value)
        else:
            model = RECORD_MODELS.get(item["category"])
            if model is None:
                raise ValueError(f"Unknown record category: {item['category']}")
            session.add(model(
                fingerprint=key,
                title=item["title"][:500],
                extraction_status=item.get("extraction_status", "pending"),
                **values,
            ))
            saved += 1
    return saved


def log_entity_mapping(session: Session, mapping: dict[str, Any]) -> None:
    existing = session.scalar(select(EntityMapping).where(
        EntityMapping.raw_name == mapping["raw_name"],
        EntityMapping.source_url == mapping["source_url"],
    ))
    if existing is None:
        session.add(EntityMapping(**mapping))


def start_run(session: Session, collector: str) -> IngestionRun:
    run = IngestionRun(collector=collector, status="running")
    session.add(run)
    session.commit()
    return run
