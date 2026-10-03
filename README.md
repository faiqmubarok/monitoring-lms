# USI Moodle LMS Checker

Aplikasi CLI untuk mengecek kelengkapan konten LMS (PPT, Video, Quiz) per kelas di Moodle USI — semester 2026/2027 Ganjil.

## Cara Install

**Prasyarat:** Python 3.10+

```bash
pip install -r requirements.txt
```

## Konfigurasi

Salin `.env.example` ke `.env` dan isi token Moodle:

```bash
cp .env.example .env
```

Edit `.env`:
```
MOODLE_URL=https://lms2.sains.ac.id
MOODLE_TOKEN=token_anda_di_sini
SEMESTER_CODE=20261
```

> ⚠ Jangan pernah commit file `.env` ke git.

## Cara Pakai

### Run normal (pakai cache)
```bash
python main.py resource/SIP.xlsx
```

### Run full refresh (ambil ulang dari Moodle)
```bash
python main.py resource/SIP.xlsx --full-refresh
```

### Tentukan nama file output
```bash
python main.py resource/SIP.xlsx --output output/laporan_minggu1.xlsx
```

### Lihat log detail
```bash
python main.py resource/SIP.xlsx --verbose
```

## Output

File Excel di folder `output/` dengan dua sheet:

| Sheet | Isi |
|---|---|
| **DATA TERBARU** | Snapshot hasil cek terkini, kolom P1–P14, status per kelas |
| **RIWAYAT CEK** | Histori setiap run — tidak pernah dihapus |

### Status LMS

| Status | Arti |
|---|---|
| 🟢 LENGKAP | P1–P14 semua ada PPT, Video, Quiz |
| 🟡 BELUM LENGKAP | Course ada tapi konten kurang |
| 🔴 COURSE TIDAK DITEMUKAN | Shortname Moodle tidak cocok |
| ⚫ BELUM KRS | Dosen belum terisi di Excel |

## Struktur Project

```
src/
  config.py          — Konfigurasi dari .env
  excel_reader.py    — Baca & filter Excel KRS
  moodle_api.py      — Moodle Web Service client
  course_matcher.py  — Matching kelas ↔ Moodle course
  content_checker.py — Parser P1–P14, detektor PPT/Video/Quiz
  report_generator.py— Generate Excel report
  cache.py           — Cache disk (JSON)
  orchestrator.py    — Koordinator utama + progress display
main.py              — Entry point CLI
```

## Filter Kelas

Hanya kelas yang memenuhi kriteria ini yang diproses:
- Kode kelas **tidak berakhiran O** (bukan kelas online)
- Ruangan: **R2A, R2B, atau R2C**
