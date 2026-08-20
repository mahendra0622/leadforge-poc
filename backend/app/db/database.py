"""
FintelliPro — Database Connection
SQLAlchemy sync engine + session factory
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from typing import Generator

from app.core.config import settings

# Render.com provides postgres:// but SQLAlchemy 2.x requires postgresql://
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

# Sync engine (for background tasks + Celery)
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.APP_ENV == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on startup."""
    Base.metadata.create_all(bind=engine)
