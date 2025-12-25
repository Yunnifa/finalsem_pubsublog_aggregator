"""
Database connection and session management with transaction support.
"""
import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from app.models import Base

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:pass@localhost:5432/aggregator_db"
)

# Create engine with connection pooling
# Using QueuePool for production with pool_pre_ping for connection health checks
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
    isolation_level="READ COMMITTED",  # Default isolation level
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def init_db():
    """Initialize database tables and default data."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    
    # Initialize stats table with default row if not exists
    with get_db_session() as db:
        from app.models import Stats
        stats = db.query(Stats).first()
        if not stats:
            stats = Stats(received=0, unique_processed=0, duplicate_dropped=0)
            db.add(stats)
            db.commit()
            logger.info("Initialized stats table with default values")
    
    logger.info("Database initialization complete")


@contextmanager
def get_db_session() -> Session:
    """
    Context manager for database sessions with automatic commit/rollback.
    
    Usage:
        with get_db_session() as db:
            # perform database operations
            db.add(obj)
            # automatically commits on success, rolls back on exception
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction failed: {e}")
        raise
    finally:
        session.close()


def get_db():
    """
    Dependency for FastAPI endpoints to get database session.
    
    Usage in FastAPI:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def update_stats_atomic(db: Session, received: int = 0, unique: int = 0, duplicate: int = 0):
    """
    Atomically update statistics using SQL UPDATE to prevent lost updates.
    
    This uses SQL-level increment (SET count = count + 1) which is safe under
    concurrent access and prevents race conditions on stats counters.
    
    Args:
        db: Database session
        received: Number of received events to add
        unique: Number of unique events to add
        duplicate: Number of duplicate events to add
    """
    from app.models import Stats
    
    # Use SQL UPDATE with arithmetic to avoid lost updates
    # This is atomic at the database level
    db.execute(
        """
        UPDATE stats 
        SET 
            received = received + :received,
            unique_processed = unique_processed + :unique,
            duplicate_dropped = duplicate_dropped + :duplicate,
            updated_at = NOW()
        WHERE id = 1
        """,
        {"received": received, "unique": unique, "duplicate": duplicate}
    )
    db.commit()
