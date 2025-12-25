"""
Data models for event schema and database tables.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, BigInteger, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class EventModel(BaseModel):
    """Pydantic model for event validation."""
    topic: str = Field(..., min_length=1, max_length=255, description="Event topic")
    event_id: str = Field(..., min_length=1, max_length=255, description="Unique event identifier")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    source: str = Field(..., min_length=1, max_length=255, description="Event source")
    payload: Dict[str, Any] = Field(..., description="Event payload data")

    @validator('timestamp')
    def validate_timestamp(cls, v):
        """Validate ISO8601 timestamp format."""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('timestamp must be valid ISO8601 format')
        return v

    class Config:
        schema_extra = {
            "example": {
                "topic": "user.login",
                "event_id": "evt-123456",
                "timestamp": "2025-12-24T01:00:00Z",
                "source": "auth-service",
                "payload": {"user_id": 42, "action": "login"}
            }
        }


class BatchEventModel(BaseModel):
    """Model for batch event submission."""
    events: list[EventModel] = Field(..., min_items=1, description="List of events")


class ProcessedEvent(Base):
    """Database model for processed events with deduplication."""
    __tablename__ = 'processed_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(255), nullable=False, index=True)
    event_id = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Unique constraint for idempotency: (topic, event_id) must be unique
    __table_args__ = (
        UniqueConstraint('topic', 'event_id', name='uq_topic_event_id'),
    )


class Stats(Base):
    """Database model for aggregator statistics."""
    __tablename__ = 'stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    received = Column(BigInteger, default=0, nullable=False)
    unique_processed = Column(BigInteger, default=0, nullable=False)
    duplicate_dropped = Column(BigInteger, default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StatsResponse(BaseModel):
    """Response model for /stats endpoint."""
    received: int = Field(..., description="Total events received")
    unique_processed: int = Field(..., description="Unique events processed")
    duplicate_dropped: int = Field(..., description="Duplicate events dropped")
    topics: int = Field(..., description="Number of distinct topics")
    uptime: float = Field(..., description="Service uptime in seconds")

    class Config:
        schema_extra = {
            "example": {
                "received": 25000,
                "unique_processed": 17500,
                "duplicate_dropped": 7500,
                "topics": 5,
                "uptime": 3600.5
            }
        }


class EventResponse(BaseModel):
    """Response model for event queries."""
    id: int
    topic: str
    event_id: str
    timestamp: str
    source: str
    payload: Dict[str, Any]
    processed_at: str

    class Config:
        orm_mode = True
