import pytest
import os
import sys
from sqlalchemy import text

# Fix Path agar import app.models dkk tidak error
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_DIR = os.path.join(BASE_DIR, 'aggregator', 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from app.database import SessionLocal, engine, Base

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture(autouse=True)
def db_cleaner():
    """Membersihkan database sebelum setiap fungsi test."""
    with SessionLocal() as session:
        # Gunakan TRUNCATE CASCADE agar semua tabel bersih dan ID mulai dari 1 lagi
        # Sesuaikan nama tabel dengan yang ada di database Anda
        session.execute(text("TRUNCATE TABLE processed_events, stats RESTART IDENTITY CASCADE;"))
        # Masukkan row stats awal agar update_stats_atomic selalu menemukan ID=1
        session.execute(text("INSERT INTO stats (id, received, unique_processed, duplicate_dropped) VALUES (1, 0, 0, 0)"))
        session.commit()
    yield