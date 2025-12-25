# UAS Sistem Terdistribusi - Pub-Sub Log Aggregator
Sistem Pub-Sub log aggregator terdistribusi dengan **Idempotent Consumer**, **Persistent Deduplication**, dan **Transaction/Concurrency Control**.

## 🏗 Arsitektur Sistem

```
┌──────────────┐
│  Publisher   │──┐ HTTP POST /publish
│   Service    │  │
└──────────────┘  ▼
           ┌─────────────────┐
           │   Aggregator    │
           │  (FastAPI API)  │
           │  + Consumer     │
           └─────────────────┘
                  │  │
       ┌──────────┘  └──────────┐
       ▼                        ▼
┌─────────────┐         ┌──────────────┐
│ PostgreSQL  │         │    Redis     │
│  (Storage)  │         │   (Broker)   │
└─────────────┘         └──────────────┘
```

**4 Services:**
- **Aggregator** (port 8080): FastAPI API + Idempotent Consumer
- **Publisher**: Event generator (25K events, 30% duplikasi)
- **PostgreSQL**: Persistent deduplication store (UNIQUE constraint)
- **Redis**: Message broker (optional)

## 🚀 Quick Start

```bash
# 1. Build dan jalankan
docker compose up --build

# 2. Verifikasi (di terminal lain)
curl http://localhost:8080/health
curl http://localhost:8080/stats

# 3. Stop
docker compose down
```

**Proses:**
- Build images → Pull PostgreSQL & Redis → Create volumes → Start services
- Publisher send 25K events (~2 menit)
- Data persisten di named volumes `pg_data` dan `broker_data`

---

## 📡 API Endpoints

### `POST /publish`
```json
{
  "events": [{
    "topic": "user.login",
    "event_id": "evt-12345",
    "timestamp": "2025-12-25T07:30:00Z",
    "source": "auth-service",
    "payload": {"user_id": 42}
  }]
}
```

**Response:**
```json
{
  "status": "success",
  "details": {
    "received": 1,
    "processed": 1,
    "duplicates": 0
  }
}
```

### `GET /events?topic=...&limit=100&offset=0`
Query events dengan filtering dan pagination.

### `GET /stats`
```json
{
  "received": 25000,
  "unique_processed": 17500,
  "duplicate_dropped": 7500,
  "topics": 5,
  "uptime": 3600.5
}
```

### `GET /health`
Database connectivity check.

---

## 🧪 Testing

```bash
# Option 1: Lokal
pytest tests/ -v

# Option 2: Docker (recommended)
docker compose up -d aggregator
docker compose exec aggregator pytest /app/tests/ -v
```

**Result:** 32/32 passed ✅

---

## 🎯 Keputusan Desain

### 1. Idempotency via UNIQUE Constraint
✅ Atomic enforcement, no distributed locks, immune to race conditions

**Alternatif:**
- ❌ Redis SET: tidak persistent by default
- ❌ Application lock: kompleks, prone to bugs

### 2. READ COMMITTED Isolation
✅ Balance consistency & performance, mencegah dirty reads

**Trade-off:** Possible non-repeatable reads (acceptable untuk log aggregator)

### 3. Atomic Stats Updates
**SQL-level:** `UPDATE stats SET count = count + 1`
✅ No lost updates under concurrent access

**vs Application-level (BAD):**
```python
# ❌ Race-prone
stats.count += 1
db.commit()
```

### 4. Named Volumes
✅ Data persisten, managed by Docker, backup-friendly

---

**Concurrency Test:** 5 threads → 1 processed, 4 duplicates → **0 race conditions** ✅

---

## 📁 Struktur Proyek

```
finalsem_pubsublog_aggregator/
├── aggregator/
│   ├── app/
│   │   ├── main.py         # FastAPI (5 endpoints)
│   │   ├── models.py       # Pydantic + SQLAlchemy
│   │   ├── database.py     # Transactions
│   │   └── consumer.py     # Idempotent consumer
│   ├── Dockerfile
│   └── requirements.txt
├── publisher/
│   ├── publisher.py
│   ├── Dockerfile
│   └── requirements.txt
├── tests/                  # 32 tests
│   ├── test_deduplication.py
│   ├── test_concurrency.py
│   ├── test_api.py
│   ├── test_performance.py
│   └── test_validation.py
├── docker-compose.yml
├── README.md
└── report.md              # Teori T1-T10
```

---

## 🔧 Troubleshooting

**Port 8080 already in use:**
```powershell
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

**Build fails:**
```bash
docker system prune -a -f
docker compose build --no-cache
```

**Tests fail:**
```bash
docker compose up -d storage
sleep 5
export DATABASE_URL="postgresql://user:pass@localhost:5432/aggregator_db"
pytest tests/ -v
```
---

## 📚 Referensi

**Buku Utama (APA 7th):**
> Tanenbaum, A. S., & Van Steen, M. (2023). *Distributed systems: Principles and paradigms* (4th ed.). Pearson Education.

**Teknologi:**
- [FastAPI](https://fastapi.tiangolo.com/)
- [PostgreSQL 16](https://www.postgresql.org/docs/16/)
- [Docker Compose](https://docs.docker.com/compose/)

---

## 🎓 Keterkaitan Bab 1-13

| Bab | Implementasi |
|-----|--------------|
| 1-2 | Pub-Sub pattern, microservices, Docker Compose |
| 3-4 | REST API, topic naming, UUID event_id |
| 5 | ISO8601 timestamps, ordering |
| 6 | Retry backoff, persistent storage, health checks |
| 7 | Idempotency, eventual consistency |
| 8 | READ COMMITTED, ACID |
| 9 | UNIQUE constraint, upsert, atomic ops |
| 10 | Non-root containers, network isolation |
| 11 | PostgreSQL volumes, durability |
| 12-13 | REST API, orchestration, observability |
