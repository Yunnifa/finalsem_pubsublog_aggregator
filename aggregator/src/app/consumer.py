import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from app.models import ProcessedEvent, EventModel
from app.database import get_db_session, update_stats_atomic

logger = logging.getLogger(__name__)

class IdempotentConsumer:
    def __init__(self):
        logger.info("IdempotentConsumer initialized")

    def process_event(self, event: EventModel, db: Session) -> bool:
        """Memproses satu event dengan PostgreSQL ON CONFLICT."""
        dt_str = event.timestamp.replace('Z', '+00:00')
        event_timestamp = datetime.fromisoformat(dt_str)

        stmt = insert(ProcessedEvent).values(
            topic=event.topic,
            event_id=event.event_id,
            timestamp=event_timestamp,
            source=event.source,
            payload=event.payload
        ).on_conflict_do_nothing(constraint='uq_topic_event_id')
        
        result = db.execute(stmt)
        return result.rowcount > 0

    def process_batch(self, events: List[EventModel]) -> Dict[str, Any]:
        processed_count = 0
        duplicate_count = 0
        
        with get_db_session() as db:
            for event in events:
                if self.process_event(event, db):
                    processed_count += 1
                else:
                    duplicate_count += 1
            
            update_stats_atomic(db, len(events), processed_count, duplicate_count)

        return {
            "received": len(events),
            "processed": processed_count,
            "duplicates": duplicate_count,
            "errors": 0
        }

consumer = IdempotentConsumer()