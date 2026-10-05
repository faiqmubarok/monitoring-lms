"""
quiz_schedule.py
Validasi jadwal quiz (open/close dates) sesuai hari kelas.

Pola:
  - Quiz P-N buka pada hari kelas minggu ke-N, pukul 00:00 WIB
  - Quiz P-N tutup 6 hari kemudian, pukul 23:59 WIB
  - Hanya P1 yang dicek (course reuse membuat P2+ ikut otomatis)
"""

from __future__ import annotations

import re
import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── Mapping nama hari Indonesia → weekday (Mon=0 .. Sun=6) ─────────────────
_DAY_MAP: dict[str, int] = {
    "senin":   0,
    "selasa":  1,
    "rabu":    2,
    "kamis":   3,
    "jumat":   4,
    "jum'at":  4,
    "sabtu":   5,
    "minggu":  6,
}

_JADWAL_DAY_RE = re.compile(r"^([a-z']+)", re.IGNORECASE)

# WIB = UTC+7
_WIB = timezone(timedelta(hours=7))


def parse_class_day(jadwal: str) -> int | None:
    """
    Ekstrak hari kelas dari string jadwal.
    Contoh: "Sabtu09:10:00-11:10:00" -> 5 (Saturday)
            "Rabu 16:40:00-18:40:00" -> 2 (Wednesday)

    Return: weekday int (0=Mon..6=Sun), atau None jika tidak dikenali.
    """
    m = _JADWAL_DAY_RE.match(jadwal.strip())
    if not m:
        return None
    day = _DAY_MAP.get(m.group(1).lower())
    if day is None:
        logger.warning("Hari tidak dikenali dari jadwal: '%s'", jadwal)
    return day


def compute_expected_dates(
    class_day: int,
    pertemuan: int,
    semester_start_week: date,
) -> tuple[datetime, datetime]:
    """
    Hitung tanggal buka/tutup quiz yang benar untuk Pertemuan N.

    Args:
        class_day           : weekday kelas (0=Mon..6=Sun)
        pertemuan           : nomor pertemuan (1..14)
        semester_start_week : tanggal Senin minggu pertama semester

    Return: (expected_open, expected_close) sebagai datetime lokal WIB (naive)
    """
    # Tanggal kelas di minggu ke-N (1-indexed)
    class_date = semester_start_week + timedelta(weeks=pertemuan - 1, days=class_day)

    # Opens: 00:00:00 WIB pada hari kelas
    expected_open = datetime(class_date.year, class_date.month, class_date.day, 0, 0, 0)

    # Closes: 23:59:00 WIB 6 hari kemudian
    close_date = class_date + timedelta(days=6)
    expected_close = datetime(close_date.year, close_date.month, close_date.day, 23, 59, 0)

    return expected_open, expected_close


def validate_quiz_dates(
    timeopen: int | None,
    timeclose: int | None,
    expected_open: datetime,
    expected_close: datetime,
) -> bool:
    """
    Bandingkan timestamp quiz (Unix epoch UTC) dengan expected dates (WIB).

    Validasi hanya berdasarkan tanggal (bukan jam persis):
      - Tanggal buka harus cocok dengan expected_open.date()
      - Tanggal tutup harus cocok dengan expected_close.date()

    Return True jika kedua tanggal cocok, False jika tidak atau data None.
    """
    if not timeopen or not timeclose:
        return False

    actual_open_local  = datetime.fromtimestamp(timeopen,  tz=_WIB).replace(tzinfo=None)
    actual_close_local = datetime.fromtimestamp(timeclose, tz=_WIB).replace(tzinfo=None)

    open_ok  = actual_open_local.date()  == expected_open.date()
    close_ok = actual_close_local.date() == expected_close.date()

    if not open_ok or not close_ok:
        logger.debug(
            "Quiz jadwal mismatch: open=%s (exp %s), close=%s (exp %s)",
            actual_open_local.date(), expected_open.date(),
            actual_close_local.date(), expected_close.date(),
        )

    return open_ok and close_ok
