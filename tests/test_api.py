"""
Tests for API endpoints.

These tests verify the correct behavior of all REST API endpoints
including validation, filtering, and response formats.
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'aggregator', 'src'))

import main
app = main.app

client = TestClient(app)


class TestAPI:
    """Test suite for API endpoints."""
    
    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code in [200, 503]  # May be unhealthy if DB not ready
        data = response.json()
        assert "status" in data
        assert "database" in data
    
    def test_publish_single_event_valid(self):
        """Test publishing a single valid event."""
        event = {
            "events": [
                {
                    "topic": "test.api",
                    "event_id": "api-test-001",
                    "timestamp": "2025-12-24T00:00:00Z",
                    "source": "api-test",
                    "payload": {"key": "value"}
                }
            ]
        }
        
        response = client.post("/publish", json=event)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "details" in data
    
    def test_publish_batch_events(self):
        """Test publishing multiple events in a batch."""
        events = {
            "events": [
                {
                    "topic": "test.batch",
                    "event_id": f"batch-{i}",
                    "timestamp": "2025-12-24T00:00:00Z",
                    "source": "api-test",
                    "payload": {"index": i}
                }
                for i in range(5)
            ]
        }
        
        response = client.post("/publish", json=events)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["details"]["received"] == 5
    
    def test_publish_invalid_event_missing_field(self):
        """Test that publishing event with missing required field fails."""
        event = {
            "events": [
                {
                    "topic": "test.invalid",
                    # Missing event_id
                    "timestamp": "2025-12-24T00:00:00Z",
                    "source": "api-test",
                    "payload": {}
                }
            ]
        }
        
        response = client.post("/publish", json=event)
        assert response.status_code == 422  # Validation error
    
    def test_publish_invalid_timestamp(self):
        """Test that invalid timestamp format is rejected."""
        event = {
            "events": [
                {
                    "topic": "test.invalid",
                    "event_id": "invalid-ts",
                    "timestamp": "not-a-timestamp",
                    "source": "api-test",
                    "payload": {}
                }
            ]
        }
        
        response = client.post("/publish", json=event)
        assert response.status_code == 422
    
    def test_get_events_without_filter(self):
        """Test retrieving events without topic filter."""
        # First publish some events
        events = {
            "events": [
                {
                    "topic": "test.get",
                    "event_id": f"get-{i}",
                    "timestamp": "2025-12-24T00:00:00Z",
                    "source": "api-test",
                    "payload": {"index": i}
                }
                for i in range(3)
            ]
        }
        client.post("/publish", json=events)
        
        # Retrieve events
        response = client.get("/events")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_events_with_topic_filter(self):
        """Test retrieving events filtered by topic."""
        # Publish events to different topics
        for topic in ["topic.a", "topic.b"]:
            events = {
                "events": [
                    {
                        "topic": topic,
                        "event_id": f"{topic}-{i}",
                        "timestamp": "2025-12-24T00:00:00Z",
                        "source": "api-test",
                        "payload": {"topic": topic}
                    }
                    for i in range(3)
                ]
            }
            client.post("/publish", json=events)
        
        # Retrieve only topic.a events
        response = client.get("/events?topic=topic.a")
        assert response.status_code == 200
        data = response.json()
        assert all(event["topic"] == "topic.a" for event in data)
    
    def test_get_events_pagination(self):
        """Test pagination parameters."""
        # Publish 20 events
        events = {
            "events": [
                {
                    "topic": "test.pagination",
                    "event_id": f"page-{i}",
                    "timestamp": "2025-12-24T00:00:00Z",
                    "source": "api-test",
                    "payload": {"index": i}
                }
                for i in range(20)
            ]
        }
        client.post("/publish", json=events)
        
        # Get first 10
        response = client.get("/events?topic=test.pagination&limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 10
        
        # Get next 10
        response = client.get("/events?topic=test.pagination&limit=10&offset=10")
        assert response.status_code == 200
        data2 = response.json()
        assert len(data2) <= 10
    
    def test_get_stats(self):
        """Test statistics endpoint."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "received" in data
        assert "unique_processed" in data
        assert "duplicate_dropped" in data
        assert "topics" in data
        assert "uptime" in data
        
        assert isinstance(data["received"], int)
        assert isinstance(data["unique_processed"], int)
        assert isinstance(data["duplicate_dropped"], int)
        assert isinstance(data["topics"], int)
        assert isinstance(data["uptime"], (int, float))
    
    def test_stats_accuracy(self):
        """Test that stats accurately reflect processed events."""
        # Clear state by getting initial stats
        initial_stats = client.get("/stats").json()
        
        # Publish 10 unique + 5 duplicate events
        unique_events = [
            {
                "topic": "test.stats",
                "event_id": f"stats-{i}",
                "timestamp": "2025-12-24T00:00:00Z",
                "source": "api-test",
                "payload": {"index": i}
            }
            for i in range(10)
        ]
        
        duplicate_events = [
            {
                "topic": "test.stats",
                "event_id": f"stats-{i}",  # Same IDs as first 5
                "timestamp": "2025-12-24T00:01:00Z",
                "source": "api-test",
                "payload": {"index": i, "dup": True}
            }
            for i in range(5)
        ]
        
        client.post("/publish", json={"events": unique_events})
        client.post("/publish", json={"events": duplicate_events})
        
        # Check stats
        final_stats = client.get("/stats").json()
        
        # Calculate deltas
        received_delta = final_stats["received"] - initial_stats["received"]
        unique_delta = final_stats["unique_processed"] - initial_stats["unique_processed"]
        dup_delta = final_stats["duplicate_dropped"] - initial_stats["duplicate_dropped"]
        
        assert received_delta == 15, "Should receive 15 total events"
        assert unique_delta == 10, "Should process 10 unique events"
        assert dup_delta == 5, "Should drop 5 duplicates"
