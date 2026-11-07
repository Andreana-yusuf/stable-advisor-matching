-- Data master contoh untuk mencoba API. Preferensi diisi lewat endpoint, bukan di sini.
-- Jalankan setelah sql/schema.sql: psql "$DATABASE_URL" -f sql/seed_contoh.sql

BEGIN;

INSERT INTO periode (kode, nama, status, tanggal_mulai, tanggal_selesai, batas_preferensi, max_preferensi)
VALUES ('2026-GANJIL', 'Periode Skripsi 2026 Ganjil', 'open',
        DATE '2026-09-01', DATE '2027-01-31', TIMESTAMPTZ '2026-11-30 23:59:59+07', 3);

INSERT INTO dosen (nidn, nama, email, bidang_keahlian) VALUES
    ('0001018501', 'Dr. Andi Pratama',   'andi.pratama@kampus.ac.id', 'Rekayasa Perangkat Lunak'),
    ('0002028702', 'Dr. Bella Kusuma',   'bella.kusuma@kampus.ac.id', 'Kecerdasan Artifisial'),
    ('0003039003', 'Dr. Candra Wijaya',  'candra.wijaya@kampus.ac.id', 'Basis Data');

INSERT INTO mahasiswa (nim, nama, email, angkatan) VALUES
    ('2210001', 'Ahmad Fauzi',   'ahmad.fauzi@kampus.ac.id',   2022),
    ('2210002', 'Bunga Lestari', 'bunga.lestari@kampus.ac.id', 2022),
    ('2210003', 'Citra Dewi',    'citra.dewi@kampus.ac.id',    2022),
    ('2210004', 'Dimas Saputra', 'dimas.saputra@kampus.ac.id', 2022),
    ('2210005', 'Eka Wulandari', 'eka.wulandari@kampus.ac.id', 2022);

INSERT INTO kuota_dosen (periode_id, dosen_id, kuota)
SELECT p.id, d.id, k.kuota
  FROM periode p
  JOIN dosen d ON d.nidn IN ('0001018501', '0002028702', '0003039003')
  JOIN (VALUES ('0001018501', 2), ('0002028702', 1), ('0003039003', 1)) AS k(nidn, kuota)
    ON k.nidn = d.nidn
 WHERE p.kode = '2026-GANJIL';

COMMIT;