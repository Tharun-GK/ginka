from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

from sqlalchemy import select

from config.settings import settings
from src.database.db import SessionLocal
from src.database.models import EntityMapping, Record

CATEGORIES = ("startup", "product", "research", "job", "news")
WORKSHEETS = {"startup": "Startups", "product": "Products", "research": "Research Papers",
              "job": "Jobs", "news": "News"}


def csv_for(category: str) -> str:
    if category not in CATEGORIES and category != "entity_mapping":
        raise ValueError(f"Unsupported export category: {category}")
    buffer = io.StringIO(newline="")
    with SessionLocal() as session:
        if category == "entity_mapping":
            records = list(session.scalars(select(EntityMapping).order_by(EntityMapping.id)))
            columns = ["raw_name", "canonical_name", "confidence", "method", "source_url", "created_at"]
            rows = [{key: getattr(record, key) for key in columns} for record in records]
        else:
            records = list(session.scalars(select(Record).where(Record.category == category).order_by(Record.id)))
            columns = ["title", "organization", "source_name", "source_url", "url", "summary",
                       "published_at", "first_seen_at", "last_seen_at", "extraction_status", "raw_data"]
            rows = []
            for record in records:
                row = {key: getattr(record, "record_url" if key == "url" else key) for key in columns}
                if category in {"startup", "product"}:
                    try:
                        row["raw_data"] = json.loads(record.raw_data)
                    except json.JSONDecodeError:
                        pass
                rows.append(row)
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


@dataclass
class SheetsExport:
    uploaded: list[str]
    skipped: list[str]
    errors: dict[str, str]


def export_to_sheets() -> SheetsExport:
    if not settings.spreadsheet_id or not settings.google_credentials_file:
        return SheetsExport([], list(WORKSHEETS.values()) + ["Entity Mapping Log"],
                            {"configuration": "Set SPREADSHEET_ID and GOOGLE_CREDENTIALS_FILE to enable Sheets export."})
    try:
        import gspread
    except ImportError as exc:
        raise RuntimeError("Install gspread to use Google Sheets export.") from exc
    client = gspread.service_account(filename=settings.google_credentials_file)
    book = client.open_by_key(settings.spreadsheet_id)
    uploaded: list[str] = []
    errors: dict[str, str] = {}
    for category, title in [*WORKSHEETS.items(), ("entity_mapping", "Entity Mapping Log")]:
        try:
            contents = list(csv.reader(io.StringIO(csv_for(category))))
            try:
                sheet = book.worksheet(title)
            except gspread.WorksheetNotFound:
                sheet = book.add_worksheet(title=title, rows=max(len(contents), 100), cols=len(contents[0]))
            sheet.clear()
            for start in range(0, len(contents), 500):
                sheet.update(contents[start:start + 500], value_input_option="RAW")
            sheet.freeze(rows=1)
            uploaded.append(title)
        except Exception as exc:
            errors[title] = str(exc)
    return SheetsExport(uploaded, [], errors)
