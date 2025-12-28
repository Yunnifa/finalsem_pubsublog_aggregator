"""
Data models for event schema and database tables.
Defines both SQLAlchemy ORM models and Pydantic validation schemas.
Updated for SQLAlchemy 2.0 and Pydantic V2 standards.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, BigInteger, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

# SQLAlchemy 2.0 standard for base class
Base = declarative_base()

# --- PYDANTIC MODELS (Validation & API) ---

class EventModel(BaseModel):
    """
    Pydantic model for event validation.
    Satisfies Requirement: Event JSON schema validation.
    """
    topic: str = Field(..., min_length=1, max_length=255, description="Event topic")
    event_id: str = Field(..., min_length=1, max_length=255, description="Unique event identifier")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    source: str = Field(..., min_length=1, max_length=255, description="Event source")
    payload: Dict[str, Any] = Field(..., description="Event payload data")

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Validate ISO8601 timestamp format (Bab 5: Time and Ordering)."""
        try:
            # Handle Z suffix and convert to offset-aware datetime
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('timestamp must be valid ISO8601 format')
        return v

    # Pydantic V2 configuration style
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "user.login",
                "event_id": "evt-123456",
                "timestamp": "2025-12-24T01:00:00Z",
                "source": "auth-service",
                "payload": {"user_id": 42, "action": "login"}
            }
        }
    )


class BatchEventModel(BaseModel):
    """Model for batch event submission (Requirement: Batch Processing)."""
    # min_items diganti menjadi min_length di Pydantic V2
    events: List[EventModel] = Field(..., min_length=1, description="List of events")


# --- SQLALCHEMY MODELS (Database Persistence) ---

class ProcessedEvent(Base):
    """
    Database model for processed events.
    BAB 9: Idempotency & Concurrency Control.
    """
    __tablename__ = 'processed_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(255), nullable=False, index=True)
    event_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # BAB 9: Unique Constraint for strong deduplication.
    __table_args__ = (
        UniqueConstraint('topic', 'event_id', name='uq_topic_event_id'),
    )


class Stats(Base):
    """
    Database model for aggregator statistics.
    BAB 8: Transactional statistics storage.
    """
    __tablename__ = 'stats'

    id = Column(Integer, primary_key=True, default=1)
    received = Column(BigInteger, default=0, nullable=False)
    unique_processed = Column(BigInteger, default=0, nullable=False)
    duplicate_dropped = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# --- RESPONSE MODELS ---

class StatsResponse(BaseModel):
    """Response model for GET /stats (Requirement: Observability)."""
    received: int
    unique_processed: int
    duplicate_dropped: int
    topics: int
    uptime: float


class EventResponse(BaseModel):
    """Response model for GET /events."""
    id: int
    topic: str
    event_id: str
    timestamp: datetime
    source: str
    payload: Dict[str, Any]
    processed_at: datetime

    # orm_mode diganti menjadi from_attributes di Pydantic V2
    model_config = ConfigDict(from_attributes=True)