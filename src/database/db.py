import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from src.database.models import Base


def _database_url() -> str:
    url = settings.database_url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _database_url()
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}
pool_options = {"pool_size": 1, "max_overflow": 0} if not DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    **pool_options,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    if IS_VERCEL and DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Vercel deployments require a persistent PostgreSQL DATABASE_URL.")
    if DATABASE_URL.startswith("sqlite:///"):
        Path(DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def session_scope():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
