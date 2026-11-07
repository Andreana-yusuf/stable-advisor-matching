-- Skema PostgreSQL Platform Alokasi Pembimbing Skripsi (Gale-Shapley).
-- Dihasilkan oleh scripts/generate_ddl.py dari app/models; jangan sunting manual.
-- Jalankan: psql "$DATABASE_URL" -f sql/schema.sql

BEGIN;

CREATE TABLE dosen (
    id SERIAL NOT NULL, 
    nidn VARCHAR(20) NOT NULL, 
    nama VARCHAR(128) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    bidang_keahlian VARCHAR(128), 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_dosen PRIMARY KEY (id), 
    CONSTRAINT uq_dosen_nidn UNIQUE (nidn), 
    CONSTRAINT uq_dosen_email UNIQUE (email)
);

CREATE TABLE mahasiswa (
    id SERIAL NOT NULL, 
    nim VARCHAR(20) NOT NULL, 
    nama VARCHAR(128) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    angkatan INTEGER NOT NULL, 
    is_active BOOLEAN DEFAULT 'true' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_mahasiswa PRIMARY KEY (id), 
    CONSTRAINT ck_mahasiswa_angkatan_positif CHECK (angkatan > 0), 
    CONSTRAINT uq_mahasiswa_nim UNIQUE (nim), 
    CONSTRAINT uq_mahasiswa_email UNIQUE (email)
);

CREATE TABLE periode (
    id SERIAL NOT NULL, 
    kode VARCHAR(32) NOT NULL, 
    nama VARCHAR(128) NOT NULL, 
    status VARCHAR(8) DEFAULT 'draft' NOT NULL, 
    tanggal_mulai DATE NOT NULL, 
    tanggal_selesai DATE NOT NULL, 
    batas_preferensi TIMESTAMP WITH TIME ZONE NOT NULL, 
    max_preferensi INTEGER DEFAULT '5' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_periode PRIMARY KEY (id), 
    CONSTRAINT ck_periode_rentang_tanggal CHECK (tanggal_selesai >= tanggal_mulai), 
    CONSTRAINT ck_periode_max_preferensi_positif CHECK (max_preferensi > 0), 
    CONSTRAINT uq_periode_kode UNIQUE (kode), 
    CONSTRAINT ck_periode_periode_status CHECK (status IN ('draft', 'open', 'tentatif', 'terkunci', 'susulan', 'selesai'))
);

CREATE TABLE alokasi (
    id SERIAL NOT NULL, 
    periode_id INTEGER NOT NULL, 
    mahasiswa_id INTEGER NOT NULL, 
    dosen_id INTEGER NOT NULL, 
    tahap VARCHAR(7) NOT NULL, 
    status VARCHAR(8) DEFAULT 'tentatif' NOT NULL, 
    peringkat_mahasiswa INTEGER, 
    peringkat_dosen INTEGER, 
    ronde INTEGER DEFAULT '0' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_alokasi PRIMARY KEY (id), 
    CONSTRAINT uq_alokasi_periode_mahasiswa UNIQUE (periode_id, mahasiswa_id), 
    CONSTRAINT ck_alokasi_ronde_non_negatif CHECK (ronde >= 0), 
    CONSTRAINT ck_alokasi_peringkat_mhs_positif CHECK (peringkat_mahasiswa IS NULL OR peringkat_mahasiswa > 0), 
    CONSTRAINT ck_alokasi_peringkat_dosen_positif CHECK (peringkat_dosen IS NULL OR peringkat_dosen > 0), 
    CONSTRAINT fk_alokasi_periode_id_periode FOREIGN KEY(periode_id) REFERENCES periode (id) ON DELETE CASCADE, 
    CONSTRAINT fk_alokasi_mahasiswa_id_mahasiswa FOREIGN KEY(mahasiswa_id) REFERENCES mahasiswa (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_alokasi_dosen_id_dosen FOREIGN KEY(dosen_id) REFERENCES dosen (id) ON DELETE RESTRICT, 
    CONSTRAINT ck_alokasi_alokasi_tahap CHECK (tahap IN ('utama', 'susulan')), 
    CONSTRAINT ck_alokasi_alokasi_status CHECK (status IN ('tentatif', 'terkunci'))
);
CREATE INDEX ix_alokasi_dosen_id ON alokasi (dosen_id);
CREATE INDEX ix_alokasi_mahasiswa_id ON alokasi (mahasiswa_id);
CREATE INDEX ix_alokasi_periode_id ON alokasi (periode_id);

CREATE TABLE kuota_dosen (
    id SERIAL NOT NULL, 
    periode_id INTEGER NOT NULL, 
    dosen_id INTEGER NOT NULL, 
    kuota INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_kuota_dosen PRIMARY KEY (id), 
    CONSTRAINT uq_kuota_periode_dosen UNIQUE (periode_id, dosen_id), 
    CONSTRAINT ck_kuota_dosen_kuota_non_negatif CHECK (kuota >= 0), 
    CONSTRAINT fk_kuota_dosen_periode_id_periode FOREIGN KEY(periode_id) REFERENCES periode (id) ON DELETE CASCADE, 
    CONSTRAINT fk_kuota_dosen_dosen_id_dosen FOREIGN KEY(dosen_id) REFERENCES dosen (id) ON DELETE RESTRICT
);
CREATE INDEX ix_kuota_dosen_dosen_id ON kuota_dosen (dosen_id);
CREATE INDEX ix_kuota_dosen_periode_id ON kuota_dosen (periode_id);

CREATE TABLE preferensi_dosen (
    id SERIAL NOT NULL, 
    periode_id INTEGER NOT NULL, 
    dosen_id INTEGER NOT NULL, 
    mahasiswa_id INTEGER NOT NULL, 
    urutan INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_preferensi_dosen PRIMARY KEY (id), 
    CONSTRAINT uq_preferensi_dosen_urutan UNIQUE (periode_id, dosen_id, urutan), 
    CONSTRAINT uq_preferensi_dosen_mhs UNIQUE (periode_id, dosen_id, mahasiswa_id), 
    CONSTRAINT ck_preferensi_dosen_urutan_positif CHECK (urutan > 0), 
    CONSTRAINT fk_preferensi_dosen_periode_id_periode FOREIGN KEY(periode_id) REFERENCES periode (id) ON DELETE CASCADE, 
    CONSTRAINT fk_preferensi_dosen_dosen_id_dosen FOREIGN KEY(dosen_id) REFERENCES dosen (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_preferensi_dosen_mahasiswa_id_mahasiswa FOREIGN KEY(mahasiswa_id) REFERENCES mahasiswa (id) ON DELETE RESTRICT
);
CREATE INDEX ix_preferensi_dosen_dosen_id ON preferensi_dosen (dosen_id);
CREATE INDEX ix_preferensi_dosen_mahasiswa_id ON preferensi_dosen (mahasiswa_id);
CREATE INDEX ix_preferensi_dosen_periode_id ON preferensi_dosen (periode_id);

CREATE TABLE preferensi_mahasiswa (
    id SERIAL NOT NULL, 
    periode_id INTEGER NOT NULL, 
    mahasiswa_id INTEGER NOT NULL, 
    dosen_id INTEGER NOT NULL, 
    urutan INTEGER NOT NULL, 
    submit_pertama_pada TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_preferensi_mahasiswa PRIMARY KEY (id), 
    CONSTRAINT uq_preferensi_mhs_urutan UNIQUE (periode_id, mahasiswa_id, urutan), 
    CONSTRAINT uq_preferensi_mhs_dosen UNIQUE (periode_id, mahasiswa_id, dosen_id), 
    CONSTRAINT ck_preferensi_mahasiswa_urutan_positif CHECK (urutan > 0), 
    CONSTRAINT fk_preferensi_mahasiswa_periode_id_periode FOREIGN KEY(periode_id) REFERENCES periode (id) ON DELETE CASCADE, 
    CONSTRAINT fk_preferensi_mahasiswa_mahasiswa_id_mahasiswa FOREIGN KEY(mahasiswa_id) REFERENCES mahasiswa (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_preferensi_mahasiswa_dosen_id_dosen FOREIGN KEY(dosen_id) REFERENCES dosen (id) ON DELETE RESTRICT
);
CREATE INDEX ix_preferensi_mahasiswa_dosen_id ON preferensi_mahasiswa (dosen_id);
CREATE INDEX ix_preferensi_mahasiswa_mahasiswa_id ON preferensi_mahasiswa (mahasiswa_id);
CREATE INDEX ix_preferensi_mahasiswa_periode_id ON preferensi_mahasiswa (periode_id);

-- Penegakan kuota di level DB: lapisan terakhir bila ada writer selain API.
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
