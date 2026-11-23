from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.database.db import DATABASE_URL, engine, init_db
from src.database.models import EntityMapping, Record
from src.database.repository import log_entity_mapping, upsert_records


def migrate(source_path: Path) -> dict[str, int]:
    if not source_path.is_file():
        raise FileNotFoundError(f"Local SQLite database not found: {source_path}")
    if DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Set DATABASE_URL to the persistent PostgreSQL destination before migrating.")

    source_engine = create_engine(f"sqlite:///{source_path.resolve().as_posix()}")
    init_db()
    with Session(source_engine) as source, Session(engine) as destination:
        destination.begin()
        local_records = list(source.scalars(select(Record).order_by(Record.id)))
        records = [{
            "category": record.category,
            "title": record.title,
            "organization": record.organization,
            "source_name": record.source_name,
            "source_url": record.source_url,
            "url": record.record_url,
            "summary": record.summary,
            "raw_data": record.raw_data,
            "published_at": record.published_at,
            "first_seen_at": record.first_seen_at,
            "extraction_status": record.extraction_status,
        } for record in local_records]
        inserted = upsert_records(destination, records)

        mappings = list(source.scalars(select(EntityMapping).order_by(EntityMapping.id)))
        for mapping in mappings:
            log_entity_mapping(destination, {
                "raw_name": mapping.raw_name,
                "canonical_name": mapping.canonical_name,
                "confidence": mapping.confidence,
                "method": mapping.method,
                "source_url": mapping.source_url,
                "created_at": mapping.created_at,
            })
        destination.commit()

    source_engine.dispose()
    return {"records_found": len(local_records), "records_inserted": inserted,
            "mappings_found": len(mappings)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy local GraphOne SQLite records to DATABASE_URL.")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "graphone.db")
    args = parser.parse_args()
    print(migrate(args.source))


if __name__ == "__main__":
    main()
