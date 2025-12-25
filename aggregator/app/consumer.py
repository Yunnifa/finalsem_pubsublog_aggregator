"""
Idempotent event consumer with persistent deduplication.
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import ProcessedEvent, EventModel
from app.database import get_db_session, update_stats_atomic

logger = logging.getLogger(__name__)


class IdempotentConsumer:
    """
    Consumer that ensures each event (topic, event_id) is processed exactly once.
    
    Uses database unique constraint on (topic, event_id) to enforce idempotency.
    Duplicate events are detected and logged but not processed again.
    """
    
    def __init__(self):
        self.processed_count = 0
        self.duplicate_count = 0
        logger.info("IdempotentConsumer initialized")
    
    def process_event(self, event: EventModel, db: Session = None) -> bool:
        """
        Process a single event with idempotency guarantee.
        
        Args:
            event: Event to process
            db: Optional database session (will create new one if not provided)
        
        Returns:
            True if event was newly processed, False if duplicate
        """
        should_close_db = False
        if db is None:
            db = next(get_db_session())
            should_close_db = True
        
        try:
            # Parse timestamp
            event_timestamp = datetime.fromisoformat(
                event.timestamp.replace('Z', '+00:00')
            )
            
            # Create database record
            processed_event = ProcessedEvent(
                topic=event.topic,
                event_id=event.event_id,
                timestamp=event_timestamp,
                source=event.source,
                payload=event.payload
            )
            
            # Try to insert - unique constraint will prevent duplicates
            try:
                db.add(processed_event)
                db.flush()  # Flush to detect constraint violation
                
                logger.info(
                    f"✓ Processed event: topic={event.topic}, "
                    f"event_id={event.event_id}, source={event.source}"
                )
                
                self.processed_count += 1
                return True
                
            except IntegrityError as e:
                # Duplicate detected by unique constraint
                db.rollback()
                logger.warning(
                    f"⚠ Duplicate detected: topic={event.topic}, "
                    f"event_id={event.event_id} - SKIPPED (idempotent)"
                )
                
                self.duplicate_count += 1
                return False
                
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            db.rollback()
            raise
        finally:
            if should_close_db:
                db.close()
    
    def process_batch(self, events: list[EventModel]) -> Dict[str, Any]:
        """
        Process a batch of events with idempotency.
        
        Each event in the batch is processed individually within a transaction.
        Statistics are updated atomically at the end.
        
        Args:
            events: List of events to process
        
        Returns:
            Dictionary with processing results
        """
        processed = 0
        duplicates = 0
        errors = []
        
        with get_db_session() as db:
            for event in events:
                try:
                    is_new = self.process_event(event, db)
                    if is_new:
                        processed += 1
                    else:
                        duplicates += 1
                except Exception as e:
                    error_msg = f"Failed to process event {event.event_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Atomically update statistics
            update_stats_atomic(
                db,
                received=len(events),
                unique=processed,
                duplicate=duplicates
            )
        
        result = {
            "received": len(events),
            "processed": processed,
            "duplicates": duplicates,
            "errors": len(errors)
        }
        
        logger.info(
            f"Batch processing complete: {processed} new, "
            f"{duplicates} duplicates, {len(errors)} errors out of {len(events)} total"
        )
        
        return result


# Global consumer instance
consumer = IdempotentConsumer()


def process_event_wrapper(event_data: Dict[str, Any]) -> bool:
    """
    Wrapper function for processing events from Redis queue.
    
    Args:
        event_data: Event data as dictionary
    
    Returns:
        True if processed successfully, False if duplicate
    """
    try:
        event = EventModel(**event_data)
        return consumer.process_event(event)
    except Exception as e:
        logger.error(f"Error in process_event_wrapper: {e}")
        return False
