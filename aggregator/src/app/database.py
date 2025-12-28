import os
import logging
from typing import Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/aggregator_db")

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=30,
    max_overflow=50,
    pool_pre_ping=True,
    isolation_level="READ COMMITTED"
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Inisialisasi skema database."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        from app.models import Stats
        stats = db.query(Stats).filter(Stats.id == 1).first()
        if not stats:
            db.add(Stats(id=1, received=0, unique_processed=0, duplicate_dropped=0))
            db.commit()

@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager untuk transaksi manual ACID."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_db() -> Generator[Session, None, None]:
    """Dependency untuk FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def update_stats_atomic(db: Session, received: int = 0, unique: int = 0, duplicate: int = 0):
    """BAB 9: Atomic Increment langsung di level database."""
    db.execute(
        text("""
            UPDATE stats 
            SET received = received + :received,
                unique_processed = unique_processed + :unique,
                duplicate_dropped = duplicate_dropped + :duplicate
            WHERE id = 1
        """),
        {"received": received, "unique": unique, "duplicate": duplicate}
    )
    db.flush()