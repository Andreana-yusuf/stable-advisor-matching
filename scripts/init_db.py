"""Buat tabel untuk development lokal: python -m scripts.init_db

Produksi: pakai sql/schema.sql (atau Alembic) agar trigger kuota ikut terbuat.
"""

from __future__ import annotations

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine

if __name__ == "__main__":
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Tabel dibuat di {engine.url!r}: {', '.join(sorted(Base.metadata.tables))}")