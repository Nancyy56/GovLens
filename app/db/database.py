"""
SQLAlchemy database configuration and session management.

Provides the database engine, session factory, and dependency
injection utilities for database access across the application.
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.constants import (
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT,
    DB_POOL_RECYCLE,
)

# Create database engine with connection pooling
# Pool settings optimize for typical web application workloads
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
)

# Create session factory bound to the engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all ORM models.

    A typed DeclarativeBase keeps model definitions on SQLAlchemy 2.0 APIs and
    gives Alembic one metadata object for schema generation.
    """


def get_session() -> Generator[Session, None, None]:
    """
    Dependency function to inject database sessions into FastAPI endpoints.
    
    Yields:
        Session: SQLAlchemy session for database operations.
        
    Example:
        @router.get("/items")
        def get_items(session: Session = Depends(get_session)):
            return session.query(Item).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
