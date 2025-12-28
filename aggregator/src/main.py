"""
Main FastAPI application with REST endpoints for the aggregator service.
"""
import os
import time
import logging
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.models import (
    EventModel, BatchEventModel, StatsResponse, 
    EventResponse, ProcessedEvent, Stats
)
from app.database import get_db, init_db, update_stats_atomic
from app.consumer import consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Track service start time for uptime calculation
SERVICE_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting aggregator service...")
    init_db()
    logger.info("Aggregator service ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down aggregator service...")


app = FastAPI(
    title="Pub-Sub Log Aggregator",
    description="Distributed log aggregator with idempotent consumer and persistent deduplication",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Pub-Sub Log Aggregator",
        "status": "running",
        "uptime": time.time() - SERVICE_START_TIME
    }


@app.post("/publish", status_code=status.HTTP_201_CREATED)
async def publish_events(
    batch: BatchEventModel,
    db: Session = Depends(get_db)
):
    """
    Publish single or batch events to the aggregator.
    
    Events are validated and processed with idempotency guarantee.
    Duplicate events (same topic + event_id) are detected and skipped.
    
    Args:
        batch: Batch of events to publish
        db: Database session
    
    Returns:
        Processing results with counts
    """
    try:
        logger.info(f"Received batch of {len(batch.events)} events")
        
        # Process batch with idempotency
        result = consumer.process_batch(batch.events)
        
        return {
            "status": "success",
            "message": f"Processed {result['processed']} events, skipped {result['duplicates']} duplicates",
            "details": result
        }
        
    except Exception as e:
        logger.error(f"Error publishing events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process events: {str(e)}"
        )


@app.get("/events", response_model=List[EventResponse])
async def get_events(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    db: Session = Depends(get_db)
):
    """
    Get list of processed events with optional topic filtering.
    
    Args:
        topic: Optional topic filter
        limit: Maximum number of events to return (1-1000)
        offset: Number of events to skip for pagination
        db: Database session
    
    Returns:
        List of processed events
    """
    try:
        query = db.query(ProcessedEvent)
        
        if topic:
            query = query.filter(ProcessedEvent.topic == topic)
        
        events = query.order_by(ProcessedEvent.processed_at.desc()) \
                     .limit(limit) \
                     .offset(offset) \
                     .all()
        
        # Convert to response model
        result = []
        for event in events:
            result.append({
                "id": event.id,
                "topic": event.topic,
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
                "payload": event.payload,
                "processed_at": event.processed_at.isoformat()
            })
        
        logger.info(f"Returned {len(result)} events (topic={topic}, limit={limit}, offset={offset})")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve events: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """
    Get aggregator statistics.
    
    Returns:
        Statistics including received count, unique processed, duplicates dropped,
        number of topics, and service uptime.
    """
    try:
        # Get stats from database
        stats = db.query(Stats).first()
        
        if not stats:
            # Initialize if not exists
            stats = Stats(received=0, unique_processed=0, duplicate_dropped=0)
            db.add(stats)
            db.commit()
        
        # Count distinct topics
        topic_count = db.query(func.count(distinct(ProcessedEvent.topic))).scalar() or 0
        
        # Calculate uptime
        uptime = time.time() - SERVICE_START_TIME
        
        result = {
            "received": stats.received,
            "unique_processed": stats.unique_processed,
            "duplicate_dropped": stats.duplicate_dropped,
            "topics": topic_count,
            "uptime": round(uptime, 2)
        }
        
        logger.info(f"Stats requested: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve stats: {str(e)}"
        )


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint with database connectivity test.
    
    Returns:
        Health status and component checks
    """
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    is_healthy = db_status == "healthy"
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "database": db_status,
            "uptime": time.time() - SERVICE_START_TIME
        }
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
