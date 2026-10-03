"""
course_matcher.py
Mencocokkan setiap kelas dari Excel dengan course di Moodle.

Logika:
  1. Kelas dengan dosen kosong → BELUM KRS (skip Moodle lookup)
  2. Kelas dengan dosen → bentuk shortname, cari di Moodle
  3. Jika ditemukan → simpan course info
  4. Jika tidak ditemukan → COURSE TIDAK DITEMUKAN
"""

from __future__ import annotations

import logging
from typing import Any

from src.moodle_api import MoodleClient, MoodleAPIError, NOT_FOUND
from src.excel_reader import build_moodle_shortname, build_identity_key
from src import config

logger = logging.getLogger(__name__)

# ── Status constants ──────────────────────────────────────────────────────────
STATUS_BELUM_KRS = "BELUM KRS"
STATUS_NOT_FOUND = "COURSE TIDAK DITEMUKAN"
STATUS_FOUND = "DITEMUKAN"
STATUS_ERROR = "API ERROR"


def match_courses(
    filtered_rows: list[dict],
    client: MoodleClient,
) -> list[dict]:
    """
    Untuk setiap kelas yang lolos filter, cari course-nya di Moodle.

    Return: list[dict] — setiap item adalah row asli + info hasil lookup:
      - identity_key      : str
      - moodle_shortname  : str (expected shortname)
      - match_status      : STATUS_BELUM_KRS | STATUS_NOT_FOUND | STATUS_FOUND | STATUS_ERROR
      - course_id         : int | None
      - course_fullname   : str | None
      - course_shortname  : str | None
      - course_url        : str | None
      - match_error       : str | None  (pesan error jika ada)
    """
    semester = config.SEMESTER_CODE
    results: list[dict] = []

    for row in filtered_rows:
        kode = row.get("kode_kelas", "")
        mk = row.get("matakuliah", "")
        dosen = row.get("dosen", "").strip()

        identity = build_identity_key(kode, mk, semester)
        shortname = build_moodle_shortname(kode, mk, semester)

        result = {
            **row,
            "identity_key": identity,
            "moodle_shortname": shortname,
            "match_status": None,
            "course_id": None,
            "course_fullname": None,
            "course_shortname": None,
            "course_url": None,
            "match_error": None,
        }

        # Kasus 1: Dosen belum ada → BELUM KRS
        if not dosen:
            result["match_status"] = STATUS_BELUM_KRS
            logger.info("[BELUM KRS] %s", shortname)
            results.append(result)
            continue

        # Kasus 2: Ada dosen → cari di Moodle
        try:
            course = client.get_course_by_shortname(shortname)

            if isinstance(course, type(NOT_FOUND)):
                result["match_status"] = STATUS_NOT_FOUND
                logger.info("[NOT FOUND] %s", shortname)
            else:
                result["match_status"] = STATUS_FOUND
                result["course_id"] = course["id"]
                result["course_fullname"] = course["fullname"]
                result["course_shortname"] = course["shortname"]
                result["course_url"] = course["url"]
                logger.info("[FOUND] %s → id=%s", shortname, course["id"])

        except MoodleAPIError as exc:
            result["match_status"] = STATUS_ERROR
            result["match_error"] = str(exc)
            logger.error("[ERROR] %s: %s", shortname, exc)

        results.append(result)

    return results
