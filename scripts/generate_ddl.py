"""Regenerasi sql/schema.sql dari metadata SQLAlchemy: python -m scripts.generate_ddl"""

from __future__ import annotations

import pathlib

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401  (mendaftarkan seluruh tabel ke Base.metadata)
from app.db.base import Base

TRIGGER = """-- Penegakan kuota di level DB: lapisan terakhir bila ada writer selain API.
CREATE OR REPLACE FUNCTION alokasi_cegah_over_kuota() RETURNS trigger AS $$
DECLARE
    v_kuota  INTEGER;
    v_terisi INTEGER;
BEGIN
    SELECT kuota INTO v_kuota
      FROM kuota_dosen
     WHERE periode_id = NEW.periode_id AND dosen_id = NEW.dosen_id;

    IF v_kuota IS NULL THEN
        RAISE EXCEPTION 'Dosen % belum memiliki kuota pada periode %', NEW.dosen_id, NEW.periode_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    SELECT COUNT(*) INTO v_terisi
      FROM alokasi
     WHERE periode_id = NEW.periode_id
       AND dosen_id = NEW.dosen_id
       AND id <> NEW.id;

    IF v_terisi + 1 > v_kuota THEN
        RAISE EXCEPTION 'Kuota dosen % pada periode % terlampaui: % dari %',
            NEW.dosen_id, NEW.periode_id, v_terisi + 1, v_kuota
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_alokasi_kuota
    AFTER INSERT OR UPDATE OF dosen_id, periode_id ON alokasi
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION alokasi_cegah_over_kuota();

COMMIT;
"""


def render() -> str:
    dialect = postgresql.dialect()
    parts = [
        "-- Skema PostgreSQL Platform Alokasi Pembimbing Skripsi (Gale-Shapley).",
        "-- Dihasilkan oleh scripts/generate_ddl.py dari app/models; jangan sunting manual.",
        '-- Jalankan: psql "$DATABASE_URL" -f sql/schema.sql',
        "",
        "BEGIN;",
        "",
    ]
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip().replace("\t", "    ") + ";")
        for index in sorted(table.indexes, key=lambda i: i.name or ""):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
        parts.append("")
    parts.append(TRIGGER)
    return "\n".join(parts)


if __name__ == "__main__":
    target = pathlib.Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    isi = render()
    target.write_text(isi, encoding="utf-8")
    print(f"{target} ditulis ({len(isi.splitlines())} baris)")