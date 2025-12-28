import pytest
import threading
import sys
import os

# Memastikan jalur import benar
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator', 'src'))

from app.models import EventModel, ProcessedEvent, Stats
from app.consumer import IdempotentConsumer
from app.database import get_db_session, update_stats_atomic

class TestConcurrency:
    
    def test_concurrent_duplicate_processing(self):
        consumer = IdempotentConsumer()
        results = []
        event = EventModel(
            topic="test.concurrent", event_id="evt-concurrent-001",
            timestamp="2025-12-24T00:00:00Z", source="test-source", payload={"data": "test"}
        )
        def worker():
            with get_db_session() as db:
                results.append(consumer.process_event(event, db))
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert results.count(True) == 1
        assert results.count(False) == 4

    def test_parallel_batch_processing(self):
        consumer = IdempotentConsumer()
        def process_batch_thread(batch_id: int):
            events = [EventModel(
                topic=f"test.parallel.{batch_id}",
                event_id=f"evt-{batch_id}-{i}",
                timestamp="2025-12-24T00:00:00Z", source="test-source",
                payload={"index": i}
            ) for i in range(10)]
            consumer.process_batch(events)
        
        threads = [threading.Thread(target=process_batch_thread, args=(i,)) for i in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()

        with get_db_session() as db:
            assert db.query(ProcessedEvent).count() == 40

    def test_stats_consistency_under_load(self):
        def update_stats_thread():
            for _ in range(20):
                with get_db_session() as db:
                    update_stats_atomic(db, received=1, unique=1, duplicate=0)
        
        threads = [threading.Thread(target=update_stats_thread) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        with get_db_session() as db:
            stats = db.query(Stats).first()
            assert stats.received >= 200

    def test_no_lost_updates(self):
        """
        Test Lost Update.
        Note: Inisialisasi ID=1 sudah ditangani oleh fixture di conftest.py.
        """
        def increment_stats():
            for _ in range(30):
                with get_db_session() as db:
                    update_stats_atomic(db, received=1, unique=0, duplicate=0)
        
        threads = [threading.Thread(target=increment_stats) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        with get_db_session() as db:
            stats = db.query(Stats).first()
            assert stats.received == 150, f"Diharapkan 150, dapat {stats.received}"

    def test_concurrent_different_events(self):
        consumer = IdempotentConsumer()
        def process_unique_event(event_id: int):
            event = EventModel(
                topic="test.unique", event_id=f"evt-{event_id}",
                timestamp="2025-12-24T00:00:00Z", source="test-source", payload={"id": event_id}
            )
            with get_db_session() as db:
                consumer.process_event(event, db)

        threads = [threading.Thread(target=process_unique_event, args=(i,)) for i in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()

        with get_db_session() as db:
            assert db.query(ProcessedEvent).filter_by(topic="test.unique").count() == 20