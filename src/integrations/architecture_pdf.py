from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def create_architecture_pdf(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(target), pagesize=letter, rightMargin=48, leftMargin=48,
                                 topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    content = [
        Paragraph("GRAPHONE | FrontierAtlas Intelligence Graph", styles["Title"]),
        Paragraph("Prototype architecture · version 1.0", styles["Heading2"]),
        Spacer(1, 12),
        Paragraph("Public APIs/RSS → bounded asynchronous collectors → freshness, provenance, and "
                  "duplicate checks → SQLAlchemy/SQLite → entity resolution → Streamlit dashboard, "
                  "CSV, and optional Google Sheets.", styles["BodyText"]),
        Spacer(1, 14),
        Paragraph("Collectors and data integrity", styles["Heading2"]),
        Paragraph("Independent sources include arXiv, GitHub public repository search, Hacker News Show HN, "
                  "and configurable RSS feeds. Job/news records require a verifiable timestamp no older than "
                  "24 hours. Records retain both the source URL and original item URL. A database uniqueness "
                  "constraint on category and stable URL fingerprint makes repeated ingestion idempotent.",
                  styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Optional extraction and exports", styles["Heading2"]),
        Paragraph("Configured Gemini, Groq, and DeepSeek providers are tried in order. Structured extraction "
                  "is schema-validated; provider failures leave raw source data preserved. Six CSV exports are "
                  "available from the dashboard, with Google Sheets upload enabled only when configured.",
                  styles["BodyText"]),
        Spacer(1, 12),
        Paragraph("Scale-out path and limits", styles["Heading2"]),
        Paragraph("This is a local prototype, not a 500,000-record deployment. A future deployment can use "
                  "PostgreSQL, Redis plus Celery workers, object storage for large raw pages, and centralized "
                  "logs, metrics, and alerting. Rate-aware scheduling and unique database fingerprints remain "
                  "important across workers. Add vector or graph storage only for validated search needs. "
                  "Honor source terms and robots policies; do not bypass anti-bot controls.", styles["BodyText"]),
    ]
    document.build(content)
    return target


if __name__ == "__main__":
    print(create_architecture_pdf(Path(__file__).resolve().parents[2] / "docs" / "graphone-architecture.pdf"))
