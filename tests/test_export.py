import csv
import io

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, ResearchPaper
from src.integrations import export


def test_research_csv_uses_record_url_column(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine)
    with test_sessions.begin() as session:
        session.add(ResearchPaper(
            fingerprint="test-paper",
            title="A tested paper",
            organization="Test Author",
            source_name="arXiv",
            source_url="https://export.arxiv.org/api/query",
            record_url="https://arxiv.org/abs/2601.01234",
            summary="Abstract",
            raw_data="{}",
        ))
    monkeypatch.setattr(export, "SessionLocal", test_sessions)
    result = list(csv.DictReader(io.StringIO(export.csv_for("research"))))
    assert result[0]["url"] == "https://arxiv.org/abs/2601.01234"
