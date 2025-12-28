"""
Tests for event deduplication functionality.

These tests verify that the idempotent consumer correctly identifies and
skips duplicate events based on (topic, event_id) uniqueness.
"""
import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator', 'src'))

from app.models import EventModel, ProcessedEvent
from app.consumer import IdempotentConsumer
from app.database import get_db_session


class TestDeduplication:
    """Test suite for deduplication functionality."""
    
    def test_single_duplicate_detection(self):
        """Test that sending the same event twice results in one processed event."""
        consumer = IdempotentConsumer()
        
        event = EventModel(
            topic="test.topic",
            event_id="evt-001",
            timestamp="2025-12-24T00:00:00Z",
            source="test-source",
            payload={"data": "test"}
        )
        
        # Process event first time
        with get_db_session() as db:
            result1 = consumer.process_event(event, db)
            assert result1 is True, "First event should be processed"
        
        # Process same event again
        with get_db_session() as db:
            result2 = consumer.process_event(event, db)
            assert result2 is False, "Duplicate event should be skipped"
        
        # Verify only one event in database
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(
                topic="test.topic",
                event_id="evt-001"
            ).count()
            assert count == 1, "Should have exactly one event in database"
    
    def test_multiple_duplicates_in_batch(self):
        """Test that batch processing correctly handles multiple duplicates."""
        consumer = IdempotentConsumer()
        
        # Create batch with duplicates
        events = [
            EventModel(
                topic="test.batch",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"index": i}
            )
            for i in range(5)
        ]
        
        # Add duplicates of first 3 events
        events.extend([
            EventModel(
                topic="test.batch",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:01:00Z",  # Different timestamp
                source="test-source",
                payload={"index": i, "duplicate": True}
            )
            for i in range(3)
        ])
        
        # Process batch
        result = consumer.process_batch(events)
        
        assert result['received'] == 8, "Should receive 8 events"
        assert result['processed'] == 5, "Should process 5 unique events"
        assert result['duplicates'] == 3, "Should detect 3 duplicates"
        
        # Verify database has only 5 events
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(topic="test.batch").count()
            assert count == 5, "Database should have exactly 5 unique events"
    
    def test_cross_batch_deduplication(self):
        """Test that deduplication works across multiple batches."""
        consumer = IdempotentConsumer()
        
        # First batch
        batch1 = [
            EventModel(
                topic="test.cross",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"batch": 1}
            )
            for i in range(3)
        ]
        
        result1 = consumer.process_batch(batch1)
        assert result1['processed'] == 3
        
        # Second batch with some duplicates from first batch
        batch2 = [
            EventModel(
                topic="test.cross",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:01:00Z",
                source="test-source",
                payload={"batch": 2}
            )
            for i in range(1, 4)  # evt-1, evt-2, evt-3
        ]
        
        result2 = consumer.process_batch(batch2)
        assert result2['processed'] == 1, "Only evt-3 is new"
        assert result2['duplicates'] == 2, "evt-1 and evt-2 are duplicates"
        
        # Verify total unique events
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(topic="test.cross").count()
            assert count == 4, "Should have 4 unique events total"
    
    def test_same_event_id_different_topics(self):
        """Test that same event_id on different topics are treated as unique."""
        consumer = IdempotentConsumer()
        
        events = [
            EventModel(
                topic="topic.one",
                event_id="evt-shared",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"topic": "one"}
            ),
            EventModel(
                topic="topic.two",
                event_id="evt-shared",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"topic": "two"}
            )
        ]
        
        result = consumer.process_batch(events)
        
        assert result['processed'] == 2, "Both events should be processed (different topics)"
        assert result['duplicates'] == 0, "No duplicates"
        
        # Verify both in database
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(event_id="evt-shared").count()
            assert count == 2, "Should have 2 events with same ID but different topics"
    
    def test_high_duplication_rate(self):
        """Test handling of high duplication rate (50%)."""
        consumer = IdempotentConsumer()
        
        # Create 20 unique events
        unique_events = [
            EventModel(
                topic="test.high-dup",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"index": i}
            )
            for i in range(20)
        ]
        
        # Add 20 duplicates
        duplicate_events = [
            EventModel(
                topic="test.high-dup",
                event_id=f"evt-{i}",
                timestamp="2025-12-24T00:01:00Z",
                source="test-source",
                payload={"index": i, "dup": True}
            )
            for i in range(20)
        ]
        
        all_events = unique_events + duplicate_events
        
        result = consumer.process_batch(all_events)
        
        assert result['received'] == 40
        assert result['processed'] == 20, "Should process 20 unique events"
        assert result['duplicates'] == 20, "Should detect 20 duplicates"
        assert result['duplicates'] / result['received'] == 0.5, "50% duplication rate"
