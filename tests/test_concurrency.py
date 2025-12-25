"""
Tests for concurrency and race conditions.

These tests verify that the system handles concurrent access correctly
and that statistics remain consistent under parallel load.
"""
import pytest
import threading
import time
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator'))

from app.models import EventModel, ProcessedEvent, Stats
from app.consumer import IdempotentConsumer
from app.database import get_db_session, update_stats_atomic


class TestConcurrency:
    """Test suite for concurrency control."""
    
    def test_concurrent_duplicate_processing(self):
        """
        Test that multiple threads processing the same event simultaneously
        result in only one processed event (no double-processing).
        """
        consumer = IdempotentConsumer()
        results = []
        
        event = EventModel(
            topic="test.concurrent",
            event_id="evt-concurrent-001",
            timestamp="2025-12-24T00:00:00Z",
            source="test-source",
            payload={"data": "concurrent test"}
        )
        
        def process_event_thread():
            """Thread worker to process event."""
            with get_db_session() as db:
                result = consumer.process_event(event, db)
                results.append(result)
        
        # Create 5 threads processing the same event simultaneously
        threads = []
        for _ in range(5):
            t = threading.Thread(target=process_event_thread)
            threads.append(t)
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify: exactly one True (processed), four False (duplicates)
        processed_count = sum(1 for r in results if r is True)
        duplicate_count = sum(1 for r in results if r is False)
        
        assert processed_count == 1, "Exactly one thread should process the event"
        assert duplicate_count == 4, "Other 4 threads should see it as duplicate"
        
        # Verify database has only one record
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(
                topic="test.concurrent",
                event_id="evt-concurrent-001"
            ).count()
            assert count == 1, "Database should have exactly one event"
    
    def test_parallel_batch_processing(self):
        """Test multiple batches processed in parallel don't cause race conditions."""
        consumer = IdempotentConsumer()
        
        def process_batch_thread(batch_id: int):
            """Process a batch in a thread."""
            events = [
                EventModel(
                    topic=f"test.parallel.{batch_id}",
                    event_id=f"evt-{batch_id}-{i}",
                    timestamp="2025-12-24T00:00:00Z",
                    source="test-source",
                    payload={"batch": batch_id, "index": i}
                )
                for i in range(10)
            ]
            consumer.process_batch(events)
        
        # Process 4 batches in parallel
        threads = []
        for batch_id in range(4):
            t = threading.Thread(target=process_batch_thread, args=(batch_id,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify all events processed
        with get_db_session() as db:
            for batch_id in range(4):
                count = db.query(ProcessedEvent).filter(
                    ProcessedEvent.topic == f"test.parallel.{batch_id}"
                ).count()
                assert count == 10, f"Batch {batch_id} should have 10 events"
    
    def test_stats_consistency_under_load(self):
        """Test that statistics counters remain consistent under concurrent updates."""
        
        def update_stats_thread(thread_id: int, iterations: int):
            """Update stats multiple times in a thread."""
            for i in range(iterations):
                with get_db_session() as db:
                    update_stats_atomic(db, received=1, unique=1, duplicate=0)
        
        # Run 10 threads, each updating stats 20 times
        threads = []
        for thread_id in range(10):
            t = threading.Thread(target=update_stats_thread, args=(thread_id, 20))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify final counts: 10 threads * 20 iterations = 200
        with get_db_session() as db:
            stats = db.query(Stats).first()
            assert stats is not None
            # Allow some margin due to test setup
            assert stats.received >= 200, f"Expected >= 200, got {stats.received}"
            assert stats.unique_processed >= 200, f"Expected >= 200, got {stats.unique_processed}"
    
    def test_no_lost_updates(self):
        """
        Test that concurrent updates to stats don't lose increments
        (test for lost update race condition).
        """
        # Initialize stats
        with get_db_session() as db:
            stats = db.query(Stats).first()
            if stats:
                db.delete(stats)
            new_stats = Stats(received=0, unique_processed=0, duplicate_dropped=0)
            db.add(new_stats)
            db.commit()
        
        def increment_stats(count: int):
            """Increment stats counter."""
            for _ in range(count):
                with get_db_session() as db:
                    update_stats_atomic(db, received=1, unique=0, duplicate=0)
        
        # Run 5 threads, each incrementing 30 times
        threads = []
        for _ in range(5):
            t = threading.Thread(target=increment_stats, args=(30,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify: 5 * 30 = 150 increments
        with get_db_session() as db:
            stats = db.query(Stats).first()
            assert stats.received == 150, f"Expected 150, got {stats.received} (lost updates detected!)"
    
    def test_concurrent_different_events(self):
        """Test that different events processed concurrently don't interfere."""
        consumer = IdempotentConsumer()
        
        def process_unique_event(event_id: int):
            """Process a unique event."""
            event = EventModel(
                topic="test.unique",
                event_id=f"evt-{event_id}",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={"id": event_id}
            )
            with get_db_session() as db:
                consumer.process_event(event, db)
        
        # Process 20 different events concurrently
        threads = []
        for event_id in range(20):
            t = threading.Thread(target=process_unique_event, args=(event_id,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify all 20 events in database
        with get_db_session() as db:
            count = db.query(ProcessedEvent).filter_by(topic="test.unique").count()
            assert count == 20, "All 20 unique events should be processed"
