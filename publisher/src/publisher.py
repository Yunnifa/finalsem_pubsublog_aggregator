"""
Event publisher service that generates events with configurable duplication.

This service simulates a real-world event producer that may send duplicate events
due to network retries, at-least-once delivery semantics, or system failures.
"""
import os
import sys
import time
import uuid
import random
import logging
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AGGREGATOR_URL = os.getenv("AGGREGATOR_URL", "http://localhost:8080/publish")
NUM_EVENTS = int(os.getenv("NUM_EVENTS", "25000"))
DUPLICATION_RATE = float(os.getenv("DUPLICATION_RATE", "0.30"))  # 30% duplicates
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DELAY_MS = int(os.getenv("DELAY_MS", "10"))  # Delay between batches
TOPICS = ["user.login", "user.logout", "order.created", "order.completed", "payment.processed"]


class EventPublisher:
    """Event publisher with duplication simulation."""
    
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.published_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        self.unique_events = []  # Store events for duplication
        
    def generate_event(self, topic: str, event_id: str = None) -> Dict[str, Any]:
        """Generate a single event with random data."""
        if event_id is None:
            event_id = f"evt-{uuid.uuid4()}"
        
        return {
            "topic": topic,
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "publisher-service",
            "payload": {
                "user_id": random.randint(1, 1000),
                "session_id": str(uuid.uuid4()),
                "data": f"Sample data for {topic}",
                "random_value": random.random()
            }
        }
    
    def publish_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Publish a batch of events to the aggregator.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(
                self.target_url,
                json={"events": events},
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✓ Published batch of {len(events)} events")
                self.published_count += len(events)
                return True
            else:
                logger.error(f"✗ Failed to publish batch: {response.status_code} - {response.text}")
                self.error_count += len(events)
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Request failed: {e}")
            self.error_count += len(events)
            return False
    
    def run(self, num_events: int, duplication_rate: float, batch_size: int):
        """
        Run the publisher to generate and send events.
        
        Args:
            num_events: Total number of events to generate (including duplicates)
            duplication_rate: Percentage of events to duplicate (0.0 - 1.0)
            batch_size: Number of events per batch
        """
        logger.info(f"Starting publisher: {num_events} events, {duplication_rate*100}% duplication")
        logger.info(f"Target URL: {self.target_url}")
        logger.info(f"Topics: {', '.join(TOPICS)}")
        
        start_time = time.time()
        
        # Calculate unique vs duplicate events
        num_unique = int(num_events * (1 - duplication_rate))
        num_duplicates = num_events - num_unique
        
        logger.info(f"Generating {num_unique} unique events and {num_duplicates} duplicates")
        
        # Generate unique events first
        for i in range(num_unique):
            topic = random.choice(TOPICS)
            event = self.generate_event(topic)
            self.unique_events.append(event)
        
        # Create list of all events (unique + duplicates)
        all_events = self.unique_events.copy()
        
        # Add duplicates by randomly selecting from unique events
        for _ in range(num_duplicates):
            duplicate_event = random.choice(self.unique_events).copy()
            # Update timestamp to simulate retry
            duplicate_event["timestamp"] = datetime.now(timezone.utc).isoformat()
            all_events.append(duplicate_event)
            self.duplicate_count += 1
        
        # Shuffle to mix unique and duplicates
        random.shuffle(all_events)
        
        logger.info(f"Total events to publish: {len(all_events)} ({num_unique} unique + {num_duplicates} duplicates)")
        
        # Publish in batches
        for i in range(0, len(all_events), batch_size):
            batch = all_events[i:i + batch_size]
            
            # Wait for aggregator to be ready (retry on startup)
            retries = 0
            max_retries = 5
            while retries < max_retries:
                if self.publish_batch(batch):
                    break
                else:
                    retries += 1
                    if retries < max_retries:
                        wait_time = 2 ** retries  # Exponential backoff
                        logger.warning(f"Retrying in {wait_time}s... (attempt {retries}/{max_retries})")
                        time.sleep(wait_time)
            
            # Small delay between batches
            if DELAY_MS > 0 and i + batch_size < len(all_events):
                time.sleep(DELAY_MS / 1000.0)
            
            # Progress update every 10 batches
            if (i // batch_size) % 10 == 0 and i > 0:
                logger.info(f"Progress: {i}/{len(all_events)} events published")
        
        elapsed_time = time.time() - start_time
        
        # Final statistics
        logger.info("=" * 60)
        logger.info("PUBLISHING COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total events sent: {self.published_count}")
        logger.info(f"Unique events: {num_unique}")
        logger.info(f"Duplicate events: {num_duplicates}")
        logger.info(f"Expected duplication rate: {duplication_rate * 100:.1f}%")
        logger.info(f"Actual duplication rate: {(num_duplicates / len(all_events)) * 100:.1f}%")
        logger.info(f"Errors: {self.error_count}")
        logger.info(f"Time taken: {elapsed_time:.2f} seconds")
        logger.info(f"Throughput: {self.published_count / elapsed_time:.2f} events/sec")
        logger.info("=" * 60)


def main():
    """Main entry point for the publisher service."""
    logger.info("Event Publisher Service Starting...")
    
    # Wait a bit for other services to start
    logger.info("Waiting for aggregator service to be ready...")
    time.sleep(5)
    
    # Create publisher
    publisher = EventPublisher(AGGREGATOR_URL)
    
    # Run publishing
    try:
        publisher.run(
            num_events=NUM_EVENTS,
            duplication_rate=DUPLICATION_RATE,
            batch_size=BATCH_SIZE
        )
    except KeyboardInterrupt:
        logger.info("Publisher interrupted by user")
    except Exception as e:
        logger.error(f"Publisher failed with error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("Publisher service finished")


if __name__ == "__main__":
    main()
