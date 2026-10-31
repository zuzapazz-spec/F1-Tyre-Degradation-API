import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://f1:f1@localhost:5432/f1")
CACHE_DIR = ROOT / "data" / "cache"
DEGRADATION_PATH = ROOT / "models" / "degradation.json"
SEASONS = (2023, 2024, 2025)
PIT_LOSS_S = 21.0         # strata na zjazd, zależna od toru
MAX_RELIABLE_LIFE = 35    # okrążeń: powyżej tego degradacja jest ekstrapolacją