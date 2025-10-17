"""
Database Service - SQLAlchemy Setup
Provides database connection and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,  # Verify connections before using
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create base class for models
Base = declarative_base()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Database session context manager
    
    Usage:
        with get_db() as db:
            db.query(Model).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get database session (for dependency injection)
    
    Usage with FastAPI:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db_session)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Session will be closed by FastAPI


def init_db():
    """Initialize database - create all tables"""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully")


def drop_db():
    """Drop all tables - USE WITH CAUTION"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped")

