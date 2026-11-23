from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'graphone.db'}")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "20"))
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "5"))
    arxiv_results: int = int(os.getenv("ARXIV_RESULTS", "15"))
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    google_credentials_file: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "")
    spreadsheet_id: str = os.getenv("SPREADSHEET_ID", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    dashboard_password: str = os.getenv("DASHBOARD_PASSWORD", "")
    dashboard_session_secret: str = os.getenv("DASHBOARD_SESSION_SECRET", "")


settings = Settings()
