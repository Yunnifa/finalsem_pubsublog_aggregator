"""
Tests for performance and load handling.

These tests verify that the system can handle the required load
of 20,000+ events with 30%+ duplication rate.
"""
import pytest
import time
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator'))

from app.models import EventModel, ProcessedEvent
from app.consumer import IdempotentConsumer
from app.database import get_db_session


class TestPerformance:
    """Test suite for performance requirements."""
    
    def test_process_20k_events(self):
        """Test processing 20,000+ events with 30% duplication."""
        consumer = IdempotentConsumer()
        
        # Generate 15,000 unique events
        unique_count = 15000
        duplicate_count = 6500  # ~30% duplication
        total_count = unique_count + duplicate_count
        
        print(f"\nGenerating {unique_count} unique events...")
        unique_events = [
            EventModel(
                topic=f"test.perf.{i % 5}",  # 5 different topics
                event_id=f"perf-{i}",
                timestamp="2025-12-24T00:00:00Z",
                source="perf-test",
                payload={"index": i, "data": f"event-{i}"}
            )
            for i in range(unique_count)
        ]
        
        # Add duplicates
        print(f"Adding {duplicate_count} duplicates...")
        duplicate_events = [
            EventModel(
                topic=unique_events[i % unique_count].topic,
                event_id=unique_events[i % unique_count].event_id,
                timestamp="2025-12-24T00:01:00Z",
                source="perf-test",
                payload={"duplicate": True}
            )
            for i in range(duplicate_count)
        ]
        
        all_events = unique_events + duplicate_events
        
        print(f"Processing {len(all_events)} total events...")
        start_time = time.time()
        
        # Process in batches of 500
        batch_size = 500
        for i in range(0, len(all_events), batch_size):
            batch = all_events[i:i + batch_size]
            consumer.process_batch(batch)
            
            if (i // batch_size) % 10 == 0:
                print(f"  Processed {i}/{len(all_events)} events...")
        
        elapsed_time = time.time() - start_time
        
        # Verify results
        with get_db_session() as db:
            processed_count = db.query(ProcessedEvent).filter(
                ProcessedEvent.topic.like("test.perf.%")
            ).count()
        
        throughput = len(all_events) / elapsed_time
        
        print(f"\n=== Performance Test Results ===")
        print(f"Total events: {len(all_events)}")
        print(f"Unique events: {unique_count}")
        print(f"Duplicate events: {duplicate_count}")
        print(f"Duplication rate: {(duplicate_count / len(all_events)) * 100:.1f}%")
        print(f"Processed in database: {processed_count}")
        print(f"Time taken: {elapsed_time:.2f} seconds")
        print(f"Throughput: {throughput:.2f} events/sec")
        print(f"================================\n")
        
        # Assertions
        assert len(all_events) >= 20000, "Should process at least 20,000 events"
        assert processed_count == unique_count, "Should have exactly unique_count in DB"
        assert throughput > 100, "Should process at least 100 events/sec"
    
    def test_batch_performance(self):
        """Test batch processing performance."""
        consumer = IdempotentConsumer()
        
        batch_sizes = [10, 50, 100, 500]
        results = {}
        
        for batch_size in batch_sizes:
            events = [
                EventModel(
                    topic=f"test.batch-perf.{batch_size}",
                    event_id=f"batch-{batch_size}-{i}",
                    timestamp="2025-12-24T00:00:00Z",
                    source="perf-test",
                    payload={"index": i}
                )
                for i in range(1000)
            ]
            
            start_time = time.time()
            
            for i in range(0, len(events), batch_size):
                batch = events[i:i + batch_size]
                consumer.process_batch(batch)
            
            elapsed_time = time.time() - start_time
            throughput = len(events) / elapsed_time
            
            results[batch_size] = {
                "time": elapsed_time,
                "throughput": throughput
            }
        
        print("\n=== Batch Size Performance ===")
        for batch_size, metrics in results.items():
            print(f"Batch size {batch_size:3d}: {metrics['time']:.3f}s, "
                  f"{metrics['throughput']:.1f} events/sec")
        print("==============================\n")
        
        # Larger batches should generally be faster
        assert results[500]["throughput"] > results[10]["throughput"]
