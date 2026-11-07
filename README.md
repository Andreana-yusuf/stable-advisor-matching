# Platform Otomatisasi Alokasi Pembimbing Skripsi — Backend MVP

Alokasi pembimbing skripsi dengan **Gale-Shapley Student-Proposing / Deferred Acceptance**
(many-to-one dengan kuota). Hasil dijamin **stabil** (tanpa blocking pair), **student-optimal**,
dan **patuh kuota dosen**. Mahasiswa *late-register* dilayani lewat **mekanisme susulan**
yang tidak mengganggu alokasi yang sudah terkunci.

Stack: Python 3.11+ · FastAPI · SQLAlchemy 2.x · PostgreSQL (psycopg 3) · pytest.

---

## 1. Arsitektur

Prinsip utama: **algoritma adalah pure function**. Ia tidak tahu-menahu soal HTTP,
SQLAlchemy, maupun FastAPI, sehingga bisa diuji secara terisolasi dan dipakai ulang
(batch script, import data, simulasi). Service layer bertugas menjembatani DB ↔ algoritma.

```
HTTP request
    │
    ▼
app/api/routes        ← validasi bentuk request (Pydantic), auth admin
    │
    ▼
app/services          ← aturan domain: status periode, tenggat, kuota, transaksi
    │
    ├── app/services/repository.py   ← satu-satunya tempat query SQLAlchemy
    │
    ▼
app/algorithms        ← PURE: preferensi + kuota masuk, MatchingResult keluar
    │
    ▼
app/algorithms/validation.py  ← verifikasi blocking pair & kuota SEBELUM persist
    │
    ▼
PostgreSQL (app/models)
```

Arah dependensi: `api → services → algorithms`. `algorithms` tidak boleh mengimpor
`services`, `models`, atau `api`.

### Struktur berkas

```
app/
├── main.py                     # create_app(), exception handler, CORS, /health
├── core/config.py              # Settings (pydantic-settings, prefix APP_)
├── db/
│   ├── base.py                 # DeclarativeBase + naming convention constraint
│   ├── session.py              # engine & session factory lazy
│   └── mixins.py               # created_at / updated_at
├── algorithms/                 # ← DELIVERABLE 1 (tanpa I/O)
│   ├── types.py                # Assignment, MatchingResult, VerificationReport, enum
│   ├── preferences.py          # normalisasi peringkat, residual_capacity, kebijakan APPEND
│   ├── gale_shapley.py         # gale_shapley(), match_late_registrants()
│   └── validation.py           # find_blocking_pairs(), find_quota_violations(), verify_matching()
├── models/                     # ← DELIVERABLE 2
│   ├── enums.py                # PeriodeStatus, AlokasiStatus, Tahap
│   ├── periode.py  dosen.py  mahasiswa.py  preferensi.py  alokasi.py
├── schemas/                    # request/response Pydantic
├── services/
│   ├── repository.py           # seluruh akses DB
│   ├── preferensi_service.py   # validasi & simpan preferensi dua sisi
│   ├── matching_service.py     # orkestrasi eksekusi + verifikasi + persist
│   ├── alokasi_service.py      # query hasil + filter + paginasi
│   └── exceptions.py           # DomainError → HTTP status
└── api/
    ├── deps.py                 # DBSession, require_admin (X-API-Key)
    ├── router.py
    └── routes/                 # ← DELIVERABLE 3
        ├── preferensi.py  matching.py  alokasi.py

sql/schema.sql                  # DDL PostgreSQL (di-generate dari model) + trigger kuota
sql/seed_contoh.sql             # data master contoh (PostgreSQL)
scripts/generate_ddl.py         # regenerasi DDL agar sinkron dengan model
scripts/init_db.py              # create_all untuk development
scripts/seed_contoh.py          # data master contoh lintas-dialect (SQLite & PostgreSQL), idempoten
.vscode/                        # konfigurasi F5 (uvicorn, pytest, seed) + interpreter
tests/                          # ← DELIVERABLE 4 (72 test)
```

---

## 2. Algoritma

### `gale_shapley(preferensi_mahasiswa, preferensi_dosen, kuota_dosen, *, kebijakan_tak_terperingkat, urutan_pengusul) -> MatchingResult`

Deferred acceptance klasik:

1. Mahasiswa mengusul ke dosen pilihan berikutnya yang belum pernah menolak.
2. Dosen **menahan** (defer) pelamar terbaik sampai kuota penuh — belum menerima final.
3. Bila kuota penuh dan ada pelamar berperingkat lebih baik, penerima terburuk digusur
   dan kembali ke antrean pengusul.
4. Berhenti saat tidak ada proposal tersisa.

Sifat yang dijamin dan diuji:

| Sifat | Jaminan |
|---|---|
| Kestabilan | Tidak ada blocking pair pada hasil akhir |
| Student-optimal | Setiap mahasiswa mendapat pilihan terbaik yang mungkin di *semua* matching stabil (diverifikasi terhadap brute-force) |
| Kuota | Jumlah bimbingan per dosen ≤ kuota |
| Rasionalitas individual | Tidak ada pasangan yang tidak saling menerima |
| Determinisme | Hasil tidak bergantung urutan pengusul (untuk preferensi strict) |

Kompleksitas: O(total proposal × kuota) — setiap mahasiswa mengusul paling banyak
sebanyak panjang daftar preferensinya, sehingga total proposal terbatas.

**Kebijakan mahasiswa tak terperingkat dosen** (`UnrankedPolicy`):
- `reject` (default tahap utama): dosen hanya menerima mahasiswa yang ia ranking.
- `append` (default susulan): mahasiswa yang belum diranking ditaruh di dasar daftar
  dengan urutan deterministik mengikuti urutan kedatangan. Perlu karena dosen menutup
  preferensi sebelum mahasiswa late-register mendaftar.

Peringkat sintetis `append` **tidak** dicatat sebagai `peringkat_dosen` di DB (nilainya
`NULL`), supaya auditor bisa membedakan "diranking dosen" vs "diterima di dasar daftar".

### `match_late_registrants(..., alokasi_terkunci, ...) -> MatchingResult`

Mekanisme susulan:

1. `residual_capacity = kuota − jumlah alokasi terkunci` per dosen.
2. Alokasi terkunci diperlakukan sebagai **kursi permanen**: tidak ikut mengusul,
   tidak pernah digusur, walau ada late-register yang lebih diprioritaskan dosen.
3. Deferred acceptance dijalankan hanya pada mahasiswa late-register terhadap sisa kuota.
4. Hasil memuat alokasi terkunci (`is_locked=True`, `ronde=0`) **dan** alokasi baru.
5. Kestabilan diverifikasi pada **pasar residual** — kursi terkunci sudah dikeluarkan
   dari kuota. Blocking pair yang melibatkan mahasiswa terkunci sengaja dikecualikan
   karena pasangan itu dibekukan secara administratif.

Batas yang jujur: menggabungkan pasar terkunci + residual bisa menghasilkan blocking pair
yang melibatkan mahasiswa terkunci (mis. ia terkunci di pilihan kedua sementara pilihan
pertamanya kosong). Itu konsekuensi dari kebijakan "kunci tidak boleh diganggu", bukan
kegagalan algoritma. Validator mendukungnya lewat parameter `mahasiswa_terkunci`.

---

## 3. Skema database

7 tabel: 5 yang diminta + `kuota_dosen` (kuota harus per periode) dan pemisahan preferensi
per sisi (mahasiswa vs dosen) karena keduanya adalah input berbeda dari dua sisi pasar.

| Tabel | PK | FK | Constraint kunci |
|---|---|---|---|
| `periode` | id | — | `kode` unik; `tanggal_selesai >= tanggal_mulai`; `max_preferensi > 0`; status enum |
| `dosen` | id | — | `nidn` unik, `email` unik |
| `mahasiswa` | id | — | `nim` unik, `email` unik, `angkatan > 0` |
| `kuota_dosen` | id | periode→CASCADE, dosen→RESTRICT | unik(periode, dosen); `kuota >= 0` |
| `preferensi_mahasiswa` | id | periode→CASCADE, mahasiswa/dosen→RESTRICT | unik(periode, mhs, urutan); unik(periode, mhs, dosen); `urutan > 0` |
| `preferensi_dosen` | id | periode→CASCADE, dosen/mhs→RESTRICT | unik(periode, dosen, urutan); unik(periode, dosen, mhs); `urutan > 0` |
| `alokasi` | id | periode→CASCADE, mahasiswa/dosen→RESTRICT | **unik(periode, mahasiswa)** = satu pembimbing per mahasiswa; `ronde >= 0`; tahap/status enum |

Dua unique constraint pada tabel preferensi mencegah peringkat ganda **dan** dosen/mahasiswa
ganda dalam satu daftar. `ON DELETE RESTRICT` pada dosen/mahasiswa mencegah penghapusan
master data yang masih dipakai.

`sql/schema.sql` juga memasang **constraint trigger penegak kuota** (`trg_alokasi_kuota`,
deferrable) sebagai lapisan terakhir bila ada writer selain API. Service tetap menegakkan
kuota sebelum insert, jadi trigger ini jaring pengaman, bukan mekanisme utama.

> Enum disimpan sebagai `VARCHAR` + `CHECK` (bukan native enum PG) agar migration lebih
> mudah dan model tetap jalan di SQLite untuk test. `values_callable` memastikan yang
> tersimpan adalah `.value` (`'draft'`), bukan `.name` (`'DRAFT'`).

Regenerasi DDL setelah mengubah model:

```bash
python -m scripts.generate_ddl
```

---

## 4. Endpoint API

Base URL `/api`. Dokumen interaktif: `/docs`.

### `POST /api/preferensi`
Input/revisi daftar preferensi dosen oleh mahasiswa. **Replace-all**: urutan array =
peringkat (index 0 = pilihan pertama).

```json
{ "periode_id": 1, "mahasiswa_id": 10, "dosen_ids": [3, 1, 2] }
```

`201` → `{ periode_id, mahasiswa_id, dosen_ids, jumlah, late_register }`

Validasi: periode ada & belum `selesai`; mahasiswa aktif; setiap dosen punya kuota di
periode itu dan aktif; tanpa duplikat; `jumlah ≤ periode.max_preferensi`; ditolak `409`
bila alokasi mahasiswa sudah terkunci. `submit_pertama_pada` dipertahankan saat revisi,
sehingga status *late-register* tidak berubah hanya karena mahasiswa menyunting daftar.

### `POST /api/preferensi/dosen`
Peringkat mahasiswa oleh dosen (input wajib sisi lain pasar).

```json
{ "periode_id": 1, "dosen_id": 3, "mahasiswa_ids": [10, 11, 12] }
```

Ditolak `409` bila sudah ada alokasi terkunci pada periode itu — mengubah peringkat dosen
setelah penguncian akan membatalkan jaminan kestabilan pasangan yang sudah terkunci.

### `POST /api/matching/execute` — **admin** (`X-API-Key`)

```json
{
  "periode_id": 1,
  "tahap": "utama",
  "mahasiswa_ids": null,
  "kebijakan_tak_terperingkat": null,
  "kunci": true,
  "dry_run": false
}
```

- `tahap`: `utama` (seluruh pengisi preferensi) atau `susulan` (late-register).
- `mahasiswa_ids`: khusus susulan; `null` = pilih otomatis mahasiswa yang belum terkunci,
  diurutkan berdasarkan waktu submit pertama.
- `kunci`: `false` menyimpan sebagai `tentatif` untuk ditinjau; hasil tentatif bisa
  dieksekusi ulang tanpa duplikasi.
- `dry_run`: hitung + verifikasi tanpa menyimpan apa pun.

`200` → ringkasan eksekusi + `verifikasi` (jumlah blocking pair, pelanggaran kuota,
pelanggaran rasionalitas) + daftar alokasi baru.

Pengaman:
- Baris periode di-`SELECT ... FOR UPDATE` agar dua eksekusi admin tidak berjalan bersamaan.
- Hasil **diverifikasi dulu**; bila tidak stabil → `500` dan tidak ada yang dipersist.
- `utama` ditolak `409` bila sudah ada alokasi terkunci (arahkan ke `susulan`).
- `susulan` ditolak `409` bila tahap utama belum dijalankan.
- Seluruh penulisan dalam satu transaksi; `IntegrityError` (mis. trigger kuota) → `409`
  dan rollback.

### `GET /api/alokasi`

Query: `periode_id` (wajib), `mahasiswa_id`, `dosen_id`, `status`, `tahap`, `page`,
`page_size` (≤ 200).

```json
{
  "data": [
    { "id": 1, "periode_id": 1, "mahasiswa_id": 10, "nim": "2210001",
      "nama_mahasiswa": "Ahmad Fauzi", "dosen_id": 3, "nidn": "0001018501",
      "nama_dosen": "Dr. Andi Pratama", "tahap": "utama", "status": "terkunci",
      "peringkat_mahasiswa": 1, "peringkat_dosen": 2, "ronde": 1,
      "dibuat_pada": "2026-11-07T00:15:15Z" }
  ],
  "total": 1, "page": 1, "page_size": 50
}
```

### Kode error

| Status | `kode` | Arti |
|---|---|---|
| 401 | — | `X-API-Key` hilang/salah |
| 404 | `tidak_ditemukan` | periode/mahasiswa/dosen tidak ada |
| 409 | `konflik` | aturan periode/status/kuota dilanggar |
| 422 | `input_tidak_valid` / validasi Pydantic | bentuk atau isi request salah |
| 500 | `hasil_tidak_stabil` | verifikasi gagal; tidak ada data tersimpan |

---

## 5. Menjalankan

### Cara cepat — VS Code + SQLite (tanpa PostgreSQL)

Prasyarat: Python 3.11+ dan ekstensi **Python** (`ms-python.python`) di VS Code.
Konfigurasi debug sudah tersedia di `.vscode/`, jadi tidak perlu membuat `launch.json` sendiri.

1. **File → Open Folder** ke folder proyek ini.
2. Buka terminal terintegrasi (`` Ctrl+` ``) lalu:

   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate   |  Linux/macOS: source .venv/bin/activate
   pip install -r requirements-dev.txt
   cp .env.example .env               # Windows PowerShell: Copy-Item .env.example .env
   ```

3. Sunting `.env`, ganti baris database ke SQLite:

   ```dotenv
   APP_DATABASE_URL=sqlite:///./dev.db
   ```

4. `Ctrl+Shift+P` → **Python: Select Interpreter** → pilih `.venv`.
   (`.vscode/settings.json` sudah menunjuk ke sana sebagai default.)
5. **F5** → pilih **Seed: data master contoh**. Ini membuat `dev.db`, seluruh tabel,
   lalu 1 periode (`2026-GANJIL`, status `open`), 3 dosen (kuota 2/1/1), dan 5 mahasiswa.
   Skrip ini idempoten — dijalankan ulang tidak mengubah apa pun.
6. **F5** → pilih **FastAPI: uvicorn (reload)**. Server hidup di `http://localhost:8000`
   dengan auto-reload. Bila breakpoint tidak mengikat, hapus `--reload` dari `args`
   di `.vscode/launch.json` — reload menjalankan proses anak.
7. Buka **http://localhost:8000/docs** untuk Swagger UI, atau ikuti alur curl di bawah.

Dua konfigurasi F5 lain: **Pytest: seluruh test** (72 test, tanpa database eksternal)
dan **Seed** di atas. Semua bisa juga dijalankan lewat terminal biasa:

```bash
python -m scripts.seed_contoh
uvicorn app.main:app --reload --port 8000
pytest
```

> SQLite tidak memiliki trigger kuota deferred seperti PostgreSQL. Di mode ini kepatuhan
> kuota dijaga oleh algoritma + `verify_matching()` sebelum persist (dan diuji otomatis).
> Untuk produksi tetap gunakan PostgreSQL dengan `sql/schema.sql`.
>
> Seed hanya mengisi **data master**. Preferensi sengaja tidak di-seed supaya bisa
> dicoba lewat `POST /api/preferensi`. Belum ada endpoint CRUD master data — itu langkah
> berikutnya (lihat §6).

### Setup PostgreSQL

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |  Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                # lalu sunting APP_DATABASE_URL & APP_ADMIN_API_KEY
```

Buat skema:

```bash
psql "postgresql://postgres:postgres@localhost:5432/alokasi_pembimbing" -f sql/schema.sql
psql "$DATABASE_URL" -f sql/seed_contoh.sql   # opsional, data contoh
# atau lintas-dialect lewat ORM (tanpa trigger kuota):
python -m scripts.seed_contoh
```

Jalankan API:

```bash
uvicorn app.main:app --reload --port 8000
```

### Contoh alur lengkap

Setelah `scripts.seed_contoh`: `periode_id=1`, dosen `1..3` (kuota 2/1/1 = 4 kursi),
mahasiswa `1..5`. Karena kursi < pendaftar, satu mahasiswa tidak teralokasi — itulah
kandidat alami untuk mekanisme susulan.

Perintah di bawah untuk Git Bash / Linux / macOS. Di PowerShell pakai `curl.exe`
dan kutip ganda escaped, atau lebih mudah: lewat Swagger UI di `/docs`.

```bash
B=http://localhost:8000
K=dev-admin-key                      # nilai APP_ADMIN_API_KEY di .env

# 1. Preferensi mahasiswa (boleh sebagian atau seluruh dosen)
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":1,"dosen_ids":[1,2,3]}'
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":2,"dosen_ids":[1,2]}'
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":3,"dosen_ids":[2,1]}'
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":4,"dosen_ids":[3,1]}'
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":5,"dosen_ids":[1,3]}'

# 2. Preferensi dosen (peringkat mahasiswa)
curl -X POST $B/api/preferensi/dosen -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"dosen_id":1,"mahasiswa_ids":[1,2,5,3,4]}'
curl -X POST $B/api/preferensi/dosen -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"dosen_id":2,"mahasiswa_ids":[3,1,2]}'
curl -X POST $B/api/preferensi/dosen -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"dosen_id":3,"mahasiswa_ids":[4,5]}'

# 3. Eksekusi utama (admin). Tambahkan "dry_run":true untuk menghitung tanpa menyimpan.
curl -X POST $B/api/matching/execute -H 'Content-Type: application/json' \
     -H "X-API-Key: $K" -d '{"periode_id":1,"tahap":"utama"}'
# → 4 alokasi, verifikasi.stabil=true, mahasiswa_tidak_teralokasi=[5]

# 4. Lihat hasil
curl "$B/api/alokasi?periode_id=1"

# 5. Susulan: mahasiswa 5 menambah pilihan ke dosen yang masih punya kursi sisa.
#    (Kuota dinaikkan lebih dulu oleh admin; belum ada endpoint untuk ini.)
curl -X POST $B/api/preferensi -H 'Content-Type: application/json' \
     -d '{"periode_id":1,"mahasiswa_id":5,"dosen_ids":[1,3,2]}'
curl -X POST $B/api/matching/execute -H 'Content-Type: application/json' \
     -H "X-API-Key: $K" -d '{"periode_id":1,"tahap":"susulan"}'
# → 4 alokasi terkunci dipertahankan utuh, 1 alokasi baru (5 → dosen 2).
#    peringkat_dosen=null karena dosen 2 tidak memeringkat mahasiswa 5
#    (kebijakan APPEND: diterima di dasar daftar, bukan ditolak).
```

Catatan: `tahap:"utama"` akan menolak (409) bila sudah ada alokasi terkunci pada
periode itu — gunakan `susulan`. Mengirim preferensi mahasiswa yang alokasinya sudah
terkunci juga 409.

### Test

```bash
pytest
```

72 test, tanpa perlu PostgreSQL (SQLite in-memory + `StaticPool`):

- `tests/test_gale_shapley.py` — kasus klasik, pengusuran, kuota banyak, tak-acceptable,
  determinisme urutan, **student-optimality dibanding brute-force**, input invalid,
  dan 250 pasar acak yang semuanya wajib stabil + patuh kuota.
- `tests/test_validator_stability.py` — membuktikan validator **bisa gagal**: matching
  cacat harus terdeteksi (blocking pair kuota tersisa, pengusuran, over-kuota,
  pasangan tidak saling menerima). Tanpa ini test stabilitas bisa vacuous.
- `tests/test_susulan.py` — kunci tidak berubah, hanya sisa kuota, late-register
  berprioritas tinggi tetap tidak menggusur kunci, susulan berulang kumulatif.
- `tests/test_preferensi_api.py`, `test_matching_api.py`, `test_alokasi_api.py` —
  end-to-end lewat HTTP: auth, validasi, dry-run, tentatif, 409, filter, paginasi.

---

## 6. Keputusan desain & langkah berikutnya

**Keputusan yang diambil untuk MVP:**
- Kuota di tabel terpisah per periode, bukan kolom di `dosen` — kuota berubah tiap tahun.
- Preferensi disimpan sebagai baris-per-peringkat, bukan array/JSON — memungkinkan
  unique constraint pada (periode, subjek, urutan) dan join/reporting biasa.
- Late-register diturunkan dari `submit_pertama_pada > periode.batas_preferensi`;
  tidak perlu tabel pendaftaran terpisah.
- `AlokasiStatus` hanya `tentatif`/`terkunci`; penguncian langsung saat eksekusi
  (`kunci=true`) sehingga tidak perlu endpoint penguncian terpisah.
- Auth admin memakai satu API key (`X-API-Key`, dibandingkan dengan `compare_digest`).
  Endpoint baca belum diautentikasi.

**Sebelum produksi:**
1. Ganti `APP_ADMIN_API_KEY` (app memperingatkan bila masih nilai default) dan pindah
   ke JWT + RBAC per peran (admin/dosen/mahasiswa); batasi `GET /api/alokasi` per peran.
2. Tambahkan Alembic untuk migration; `sql/schema.sql` adalah baseline, bukan pengganti
   migration berkelanjutan.
3. Endpoint CRUD master data (periode, dosen, mahasiswa, kuota) — saat ini data master
   diisi lewat SQL/seed.
4. Rate limiting pada input preferensi dan audit log eksekusi matching.
5. Pertimbangkan menyimpan jejak proposal (`MatchingResult.rejections`) untuk audit
   banding mahasiswa; saat ini hanya dikembalikan di response, tidak dipersist.