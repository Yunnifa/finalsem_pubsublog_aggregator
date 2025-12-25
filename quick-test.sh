#!/bin/bash
# Quick verification script for the UAS Pub-Sub Log Aggregator

echo "================================"
echo "UAS Log Aggregator - Quick Test"
echo "================================"
echo ""

echo "1. Checking Docker..."
docker --version || { echo "Docker not found!"; exit 1; }

echo ""
echo "2. Checking Docker Compose..."
docker compose version || { echo "Docker Compose not found!"; exit 1; }

echo ""
echo "3. Validating docker-compose.yml..."
docker compose config > /dev/null || { echo "Invalid docker-compose.yml!"; exit 1; }
echo "✓ docker-compose.yml is valid"

echo ""
echo "4. Building images (this may take a few minutes)..."
docker compose build

echo ""
echo "5. Starting services..."
docker compose up -d storage broker

echo ""
echo "6. Waiting for database to be ready..."
sleep 10

echo ""
echo "7. Starting aggregator..."
docker compose up -d aggregator

echo ""
echo "8. Waiting for aggregator to be ready..."
sleep 5

echo ""
echo "9. Testing API endpoints..."
echo "   - GET /"
curl -s http://localhost:8080/ | head -n 5

echo ""
echo "   - GET /health"
curl -s http://localhost:8080/health | head -n 5

echo ""
echo "   - GET /stats"
curl -s http://localhost:8080/stats

echo ""
echo ""
echo "10. Running publisher (this will send 25,000 events)..."
docker compose up publisher

echo ""
echo "11. Checking final stats..."
curl -s http://localhost:8080/stats

echo ""
echo "12. Viewing some processed events..."
curl -s "http://localhost:8080/events?limit=5"

echo ""
echo ""
echo "================================"
echo "Test Complete!"
echo "================================"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose down"
echo "To clean up: docker compose down -v"
