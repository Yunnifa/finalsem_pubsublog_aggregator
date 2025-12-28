"""
Tests for schema validation.

These tests verify that event schema validation works correctly
and rejects invalid events.
"""
import pytest
from pydantic import ValidationError
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator', 'src'))

from app.models import EventModel, BatchEventModel


class TestValidation:
    """Test suite for event schema validation."""
    
    def test_valid_event(self):
        """Test that a valid event passes validation."""
        event = EventModel(
            topic="test.valid",
            event_id="evt-001",
            timestamp="2025-12-24T00:00:00Z",
            source="test-source",
            payload={"key": "value"}
        )
        
        assert event.topic == "test.valid"
        assert event.event_id == "evt-001"
    
    def test_missing_required_field(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EventModel(
                topic="test.invalid",
                # Missing event_id
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={}
            )
        
        assert "event_id" in str(exc_info.value)
    
    def test_invalid_timestamp_format(self):
        """Test that invalid timestamp format is rejected."""
        with pytest.raises(ValidationError):
            EventModel(
                topic="test.invalid",
                event_id="evt-001",
                timestamp="not-a-valid-timestamp",
                source="test-source",
                payload={}
            )
    
    def test_empty_topic(self):
        """Test that empty topic is rejected."""
        with pytest.raises(ValidationError):
            EventModel(
                topic="",  # Empty topic
                event_id="evt-001",
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={}
            )
    
    def test_empty_event_id(self):
        """Test that empty event_id is rejected."""
        with pytest.raises(ValidationError):
            EventModel(
                topic="test.valid",
                event_id="",  # Empty event_id
                timestamp="2025-12-24T00:00:00Z",
                source="test-source",
                payload={}
            )
    
    def test_batch_validation(self):
        """Test batch event validation."""
        batch = BatchEventModel(
            events=[
                EventModel(
                    topic="test.batch",
                    event_id=f"evt-{i}",
                    timestamp="2025-12-24T00:00:00Z",
                    source="test-source",
                    payload={"index": i}
                )
                for i in range(3)
            ]
        )
        
        assert len(batch.events) == 3
    
    def test_empty_batch_rejected(self):
        """Test that empty batch is rejected."""
        with pytest.raises(ValidationError):
            BatchEventModel(events=[])
    
    def test_various_timestamp_formats(self):
        """Test that various valid ISO8601 formats are accepted."""
        valid_timestamps = [
            "2025-12-24T00:00:00Z",
            "2025-12-24T00:00:00+00:00",
            "2025-12-24T00:00:00.000Z",
            "2025-12-24T12:30:45+08:00",
        ]
        
        for ts in valid_timestamps:
            event = EventModel(
                topic="test.timestamp",
                event_id="evt-ts",
                timestamp=ts,
                source="test-source",
                payload={}
            )
            assert event.timestamp == ts
