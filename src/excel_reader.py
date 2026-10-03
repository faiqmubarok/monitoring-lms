"""
excel_reader.py
Membaca file Excel KRS dari SIP dan memfilter kelas yang relevan.

Filter:
  1. Kode kelas (kolom 'Kelas' pertama / kode) TIDAK berakhiran 'O' (case-insensitive)
  2. Ruangan (kolom 'Kelas' kedua di SIP) ada di ALLOWED_ROOMS
  3. Deteksi header secara fleksibel — tidak bergantung pada nomor kolom.

Menggunakan parser XML langsung untuk menghindari masalah kompatibilitas
openpyxl stylesheet pada file yang di-generate tool tertentu.
"""

from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def normalize_mk_for_moodle(matakuliah: str) -> str:
    """
    Normalisasi nama matakuliah agar cocok dengan shortname Moodle USI.

    Pola yang diamati di Moodle USI:
      - Nama MK di Excel: 'PSI204 - Perilaku dan Proses Mental'
      - Nama MK di Moodle: 'Perilaku dan Proses Mental'

    Transformasi:
      1. Hapus kode MK di depan: 'PSI204 - ', 'USI102 - ', 'AKT2011 - ', dll.
      2. Hapus suffix ' Kelas Gabungan' (case-insensitive)
      3. Strip whitespace

    Contoh:
      'PSI204 - Perilaku dan Proses Mental'          → 'Perilaku dan Proses Mental'
      'USI102 - Pancasila Kelas Gabungan'             → 'Pancasila'
      'FIC101 - Pengantar Teknologi Informasi KG'     → 'Pengantar Teknologi Informasi'
      'Psikologi Komunikasi'                          → 'Psikologi Komunikasi'  (tidak berubah)
    """
    mk = matakuliah.strip()
    # Hapus kode MK: huruf besar + angka diikuti ' - '
    mk = re.sub(r"^[A-Z][A-Z0-9]* - ", "", mk)
    # Hapus suffix 'Kelas Gabungan'
    mk = re.sub(r"\s+Kelas Gabungan\s*$", "", mk, flags=re.IGNORECASE)
    return mk.strip()

from src.config import ALLOWED_ROOMS

logger = logging.getLogger(__name__)

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# ── Alias header yang dikenali (lowercase + strip) ───────────────────────────
_HEADER_ALIASES: dict[str, str] = {
    "no": "no",
    "kelas": "kode_kelas",       # kemunculan pertama → kode kelas (kolom C)
    "matakuliah": "matakuliah",
    "mata kuliah": "matakuliah",
    "sks": "sks",
    "smt": "smt",
    "jadwal": "jadwal",
    "dosen pengajar": "dosen",
    "dosen": "dosen",
    "prodi": "prodi",
    "peserta / kuota": "peserta_kuota",
    "peserta": "peserta_kuota",
    "ruangan": "ruangan",        # kolom L di SIP (nama ruangan fisik)
    "kampus": "kampus",
    "status": "status_kelas",    # kolom N di SIP: Buka / Tutup
    "mbkm": "mbkm",
    "lms": "lms",
}


def _col_letter_to_index(col_str: str) -> int:
    """Konversi referensi kolom Excel (A, B, ..., Z, AA, ...) ke index 1-based."""
    result = 0
    for ch in col_str.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result


def _parse_cell_ref(ref: str) -> tuple[int, int]:
    """
    Parsing referensi sel seperti 'A1', 'C12', 'AA5' menjadi (col_index, row_index).
    col_index dan row_index keduanya 1-based.
    """
    m = re.match(r"([A-Z]+)(\d+)", ref.upper())
    if not m:
        raise ValueError(f"Referensi sel tidak valid: {ref}")
    return _col_letter_to_index(m.group(1)), int(m.group(2))


def _read_sheet_xml(xlsx_path: Path) -> list[dict[int, str]]:
    """
    Baca xl/worksheets/sheet1.xml dari file XLSX secara langsung.
    Kembalikan list of dicts: [{col_index: value_str, ...}, ...] per row.
    Row index di-derive dari nomor baris XML (1-based).
    """
    with zipfile.ZipFile(xlsx_path) as zf:
        with zf.open("xl/worksheets/sheet1.xml") as f:
            tree = ET.parse(f)

    root = tree.getroot()
    ns = {"x": _NS}

    # Kumpulkan semua sel ke dalam struktur {row_number: {col_index: value}}
    rows_data: dict[int, dict[int, str]] = {}

    for c_el in root.findall(".//x:c", ns):
        ref = c_el.get("r", "")
        if not ref:
            continue

        col_idx, row_num = _parse_cell_ref(ref)

        # Baca nilai: inlineStr (t='is') atau shared string (t='s') atau numeric
        t = c_el.get("t", "")
        if t == "inlineStr":
            is_el = c_el.find("x:is/x:t", ns)
            value = is_el.text if is_el is not None and is_el.text else ""
        else:
            v_el = c_el.find("x:v", ns)
            value = v_el.text if v_el is not None and v_el.text else ""

        value = value.strip()

        if row_num not in rows_data:
            rows_data[row_num] = {}
        rows_data[row_num][col_idx] = value

    # Kembalikan sebagai list berurutan per row
    max_row = max(rows_data.keys()) if rows_data else 0
    result: list[dict[int, str]] = []
    for r in range(1, max_row + 1):
        result.append(rows_data.get(r, {}))

    return result


def _find_header_row(
    rows: list[dict[int, str]],
) -> tuple[int, dict[int, str]]:
    """
    Cari baris header dengan mendeteksi baris yang mengandung 'No' dan 'Kelas'.
    Kembalikan (header_row_index_0based, {col_index: field_name}).
    """
    for row_idx, row in enumerate(rows):
        values_lower = {col: v.lower() for col, v in row.items()}

        has_no = any(v == "no" for v in values_lower.values())
        has_kelas = any(v == "kelas" for v in values_lower.values())

        if has_no and has_kelas:
            col_map: dict[int, str] = {}
            kelas_count = 0

            # Urutkan berdasarkan col_index agar duplikat 'Kelas' ditangani runtut
            for col_idx in sorted(row.keys()):
                raw_val = row[col_idx]
                lower_val = raw_val.lower()

                if lower_val == "kelas":
                    kelas_count += 1
                    if kelas_count == 1:
                        col_map[col_idx] = "kode_kelas"   # kolom C
                    else:
                        col_map[col_idx] = "ruangan_kelas"  # kolom K (R2A, R1, dll)
                elif lower_val in _HEADER_ALIASES and lower_val != "kelas":
                    field = _HEADER_ALIASES[lower_val]
                    col_map[col_idx] = field

            logger.debug("Header row di index %d: %s", row_idx, col_map)
            return row_idx, col_map

    raise ValueError(
        "Tidak dapat menemukan baris header. "
        "Pastikan file memiliki kolom 'No' dan 'Kelas'."
    )


def _is_online_class(kode_kelas: str) -> bool:
    """Kelas online = kode berakhiran 'O' (case-insensitive)."""
    return kode_kelas.upper().endswith("O")


def _is_allowed_room(ruangan: str) -> bool:
    """Cek apakah ruangan masuk ALLOWED_ROOMS (R2A/R2B/R2C)."""
    return ruangan.upper() in ALLOWED_ROOMS


def read_and_filter(filepath: str | Path) -> tuple[list[dict], dict]:
    """
    Baca file Excel KRS dan kembalikan:
      - filtered_rows : list[dict] kelas yang lolos filter
      - summary       : dict statistik

    Field per dict: kode_kelas, matakuliah, sks, smt, jadwal, dosen,
                    prodi, peserta_kuota, ruangan_kelas, ruangan, kampus,
                    status, mbkm, lms
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File Excel tidak ditemukan: {filepath}")

    logger.info("Membaca file Excel: %s", filepath)

    rows_raw = _read_sheet_xml(filepath)
    header_idx, col_map = _find_header_row(rows_raw)

    total_rows = 0
    skipped_no_kode = 0
    skipped_online = 0
    skipped_wrong_room = 0
    filtered_rows: list[dict] = []

    for row in rows_raw[header_idx + 1 :]:
        if not row:
            skipped_no_kode += 1
            continue

        row_data: dict[str, str] = {}
        for col_idx, field_name in col_map.items():
            row_data[field_name] = row.get(col_idx, "")

        kode_kelas = row_data.get("kode_kelas", "").strip()
        if not kode_kelas:
            skipped_no_kode += 1
            continue

        total_rows += 1

        # Filter 1: Bukan kelas online
        if _is_online_class(kode_kelas):
            skipped_online += 1
            continue

        # Filter 2: Ruangan harus R2A/R2B/R2C
        # Di SIP kolom K (ruangan_kelas) berisi R2A, R2B, R2C, R1, dll.
        ruangan_kelas = row_data.get("ruangan_kelas", "").strip().upper()
        if not _is_allowed_room(ruangan_kelas):
            skipped_wrong_room += 1
            continue

        # Normalisasi
        row_data["kode_kelas"] = kode_kelas.upper()
        row_data["ruangan_kelas"] = ruangan_kelas
        row_data["matakuliah"] = row_data.get("matakuliah", "").strip()
        row_data["dosen"] = row_data.get("dosen", "").strip()

        filtered_rows.append(row_data)

    summary = {
        "total_rows": total_rows,
        "filtered": len(filtered_rows),
        "skipped_no_kode": skipped_no_kode,
        "skipped_online": skipped_online,
        "skipped_wrong_room": skipped_wrong_room,
    }

    logger.info(
        "Hasil baca: total=%d | lolos=%d | skip_online=%d | skip_ruangan=%d",
        total_rows,
        len(filtered_rows),
        skipped_online,
        skipped_wrong_room,
    )

    return filtered_rows, summary


def build_identity_key(kode_kelas: str, matakuliah: str, semester_code: str) -> str:
    """
    Buat primary key unik untuk setiap kelas.
    Format: {KODE_KELAS}|{MATAKULIAH_STRIP}|{SEMESTER}
    Dosen tidak dimasukkan ke key karena bisa berubah.
    """
    return f"{kode_kelas.upper().strip()}|{matakuliah.strip()}|{semester_code}"


def build_moodle_shortname(kode_kelas: str, matakuliah: str, semester_code: str) -> str:
    """
    Bentuk shortname Moodle sesuai format USI:
    {kode_kelas}_{nama_matakuliah}_{semester_code}

    Nama matakuliah: hanya trim whitespace, TIDAK diubah huruf besar/kecil
    karena nama dipakai untuk pencarian shortname Moodle yang case-sensitive.
    """
    kode = kode_kelas.upper().strip()
    mk = matakuliah.strip()
    return f"{kode}_{mk}_{semester_code}"


def build_identity_key(kode_kelas: str, matakuliah: str, semester_code: str) -> str:
    """
    Primary key unik per kelas — dosen tidak dimasukkan karena bisa berubah.
    Format: {KODE_KELAS}|{MATAKULIAH}|{SEMESTER}
    """
    return f"{kode_kelas.upper().strip()}|{matakuliah.strip()}|{semester_code}"


def build_moodle_shortname(kode_kelas: str, matakuliah: str, semester_code: str) -> str:
    """
    Shortname Moodle sesuai format USI:
      {kode_kelas}_{nama_matakuliah_normalized}_{semester_code}

    Nama matakuliah di-normalisasi:
      - Hapus kode MK di depan (misal 'PSI204 - ')
      - Hapus suffix 'Kelas Gabungan'

    Contoh:
      build_moodle_shortname('26FA', 'PSI204 - Perilaku dan Proses Mental', '20261')
      → '26FA_Perilaku dan Proses Mental_20261'
    """
    kode = kode_kelas.upper().strip()
    mk_normalized = normalize_mk_for_moodle(matakuliah)
    return f"{kode}_{mk_normalized}_{semester_code}"
