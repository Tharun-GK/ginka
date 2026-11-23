from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.db import Base
from src.database.repository import fingerprint, upsert_records

test_engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=test_engine)


def test_fingerprint_deduplicates_and_requires_valid_provenance():
    Base.metadata.create_all(test_engine)
    record = {"category": "news", "title": "AI news", "organization": "",
              "source_name": "Example RSS", "source_url": "https://example.com/feed.xml",
              "url": "https://example.com/story", "summary": "", "raw_data": {}}
    with TestSession.begin() as session:
        assert upsert_records(session, [record, record]) == 1
        assert upsert_records(session, [record]) == 0
    assert fingerprint("news", record["url"], record["title"]) == fingerprint(
        "news", record["url"], record["title"])


def test_records_reject_non_http_urls():
    Base.metadata.create_all(test_engine)
    record = {"category": "news", "title": "bad", "source_name": "source",
              "source_url": "https://example.com", "url": "file:///private", "raw_data": {}}
    with TestSession.begin() as session:
        try:
            upsert_records(session, [record])
        except ValueError as exc:
            assert "HTTP(S)" in str(exc)
        else:
            raise AssertionError("invalid URL was accepted")
