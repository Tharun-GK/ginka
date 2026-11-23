from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from src.collectors import job_collector, news_collector, product_collector, research_collector, startup_collector
from config.settings import settings
from src.database.db import SessionLocal, init_db
from src.database.models import IngestionRun, Record
from src.database.repository import log_entity_mapping, upsert_records
from src.llm.extraction import extract
from src.resolver.entity_resolver import EntityResolver

log = logging.getLogger(__name__)
COLLECTORS = {
    "startup": startup_collector.collect,
    "product": product_collector.collect,
    "research": research_collector.collect,
    "job": job_collector.collect,
    "news": news_collector.collect,
}


async def run_collector(name: str) -> dict:
    if name not in COLLECTORS:
        raise ValueError(f"Unknown collector: {name}")
    init_db()
    with SessionLocal() as session:
        run = IngestionRun(collector=name, status="running")
        session.add(run)
        session.commit()
        run_id = run.id
    try:
        records = await COLLECTORS[name]()
        resolver = EntityResolver()
        for item in records:
            organization = item.get("organization")
            if organization and name in {"startup", "product"}:
                match = resolver.resolve(organization)
                item["organization"] = match["canonical_name"]
                item["_entity_mapping"] = match
            if item.get("summary") and any((settings.gemini_api_key, settings.groq_api_key,
                                            settings.deepseek_api_key)):
                extraction = await extract(item["summary"])
                if extraction:
                    item["summary"] = extraction.summary or item["summary"]
                    item["raw_data"]["llm_extraction"] = extraction.model_dump()
                    item["extraction_status"] = "complete"
                else:
                    item["extraction_status"] = "failed"
        with SessionLocal.begin() as session:
            saved = upsert_records(session, records)
            for item in records:
                mapping = item.get("_entity_mapping")
                if mapping:
                    log_entity_mapping(session, {
                        "raw_name": mapping["raw_name"],
                        "canonical_name": mapping["canonical_name"],
                        "confidence": mapping["confidence"],
                        "method": mapping["method"],
                        "source_url": item["source_url"],
                    })
            run = session.get(IngestionRun, run_id)
            run.status = "completed"
            run.records_found = len(records)
            run.records_saved = saved
            run.finished_at = datetime.now(timezone.utc)
        log.info("%s collector completed: fetched=%d new=%d", name, len(records), saved)
        return {"collector": name, "found": len(records), "saved": saved, "status": "completed"}
    except Exception as exc:
        with SessionLocal.begin() as session:
            run = session.get(IngestionRun, run_id)
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = datetime.now(timezone.utc)
        log.exception("%s collector failed", name)
        return {"collector": name, "found": 0, "saved": 0, "status": "failed", "error": str(exc)}


async def run_all() -> list[dict]:
    return await asyncio.gather(*(run_collector(name) for name in COLLECTORS))


def recent_records(category: str | None = None) -> list[Record]:
    init_db()
    with SessionLocal() as session:
        query = select(Record).order_by(Record.published_at.desc(), Record.first_seen_at.desc())
        if category:
            query = query.where(Record.category == category)
        return list(session.scalars(query))


def recent_runs() -> list[IngestionRun]:
    init_db()
    with SessionLocal() as session:
        return list(session.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(50)))
