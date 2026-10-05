"""
moodle_api.py
Moodle Web Service API client untuk USI LMS Checker.

Fitur:
  - POST ke /webservice/rest/server.php
  - Retry otomatis dengan exponential backoff
  - Rate limiting (max concurrent requests dijaga di pemanggil)
  - Token TIDAK pernah dicetak ke log/output
  - Error handling per-request (tidak berhenti total)

API yang digunakan:
  1. core_course_get_courses_by_field  → cari course by shortname
  2. core_course_get_contents          → ambil struktur section & module
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src import config

logger = logging.getLogger(__name__)

# Sentinel untuk membedakan "tidak ditemukan" vs "error"
class _NotFound:
    pass

NOT_FOUND = _NotFound()


class MoodleAPIError(Exception):
    """Raised ketika Moodle API mengembalikan error yang tidak bisa di-retry."""


class MoodleClient:
    """
    Client untuk Moodle Web Service REST API.

    Penggunaan:
        client = MoodleClient()
        result = client.get_course_by_shortname("26FA_Psikologi Komunikasi_20261")
    """

    _API_PATH = "/webservice/rest/server.php"

    def __init__(self) -> None:
        self._base_url = config.MOODLE_URL
        self._timeout = config.API_TIMEOUT
        self._retry_count = config.API_RETRY_COUNT
        self._retry_delay = config.API_RETRY_DELAY
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})

    def _get_token(self) -> str:
        """Ambil token dari config — TIDAK di-cache di atribut publik."""
        return config.get_moodle_token()

    def _request(self, wsfunction: str, params: dict[str, Any]) -> Any:
        """
        Kirim POST request ke Moodle API dengan retry.

        Return: parsed JSON response
        Raise:  MoodleAPIError jika semua retry gagal atau response error fatal
        """
        url = f"{self._base_url}{self._API_PATH}"
        payload = {
            "wstoken": self._get_token(),
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **params,
        }

        last_error: Exception | None = None

        for attempt in range(1, self._retry_count + 1):
            try:
                resp = self._session.post(url, data=payload, timeout=self._timeout)
                resp.raise_for_status()
                data = resp.json()

                # Moodle mengembalikan {"exception": "...", "message": "..."} saat error
                if isinstance(data, dict) and "exception" in data:
                    msg = data.get("message", "Unknown Moodle error")
                    error_code = data.get("errorcode", "")

                    # Token invalid / akses ditolak → tidak perlu retry
                    if error_code in ("invalidtoken", "accessdenied", "nopermissions"):
                        raise MoodleAPIError(
                            f"Moodle API error (fatal) [{wsfunction}]: {msg}"
                        )

                    # Course tidak ditemukan → kembalikan sentinel, bukan error
                    if error_code == "invalidfieldname" or "not found" in msg.lower():
                        return NOT_FOUND

                    # Error lain → retry
                    raise requests.RequestException(f"Moodle soft error: {msg}")

                return data

            except requests.RequestException as exc:
                last_error = exc
                if attempt < self._retry_count:
                    wait = self._retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "[%s] Percobaan %d/%d gagal, retry dalam %.1fs: %s",
                        wsfunction, attempt, self._retry_count, wait, exc,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "[%s] Semua %d percobaan gagal: %s",
                        wsfunction, self._retry_count, exc,
                    )

        raise MoodleAPIError(
            f"API request gagal setelah {self._retry_count} percobaan "
            f"[{wsfunction}]: {last_error}"
        )

    # ── Public API methods ────────────────────────────────────────────────────

    def get_course_by_shortname(self, shortname: str) -> dict | _NotFound:
        """
        Cari course berdasarkan shortname.

        Jika tidak ditemukan, coba variasi dengan trailing space di komponen nama
        MK (untuk menangani data Moodle yang punya spasi ekstra).

        Return:
          - dict berisi data course jika ditemukan
          - NOT_FOUND jika tidak ada course dengan shortname tersebut
          - Raise MoodleAPIError jika ada error fatal
        """
        logger.debug("get_course_by_shortname: %s", shortname)

        result = self._try_shortname(shortname)
        if not isinstance(result, _NotFound):
            return result

        # Fallback: Moodle kadang menyimpan nama MK dengan trailing space.
        # Format shortname: {kode}_{nama_mk}_{semester}
        # Coba tambahkan spasi sebelum underscore terakhir.
        parts = shortname.rsplit("_", 1)
        if len(parts) == 2:
            fallback = f"{parts[0]} _{parts[1]}"
            logger.debug("get_course_by_shortname fallback (trailing space): %s", fallback)
            result = self._try_shortname(fallback)
            if not isinstance(result, _NotFound):
                return result

        return NOT_FOUND

    def _try_shortname(self, shortname: str) -> dict | _NotFound:
        """Helper: satu lookup by shortname, kembalikan dict atau NOT_FOUND."""
        result = self._request(
            "core_course_get_courses_by_field",
            {"field": "shortname", "value": shortname},
        )

        if isinstance(result, _NotFound):
            return NOT_FOUND

        courses = result.get("courses", [])
        if not courses:
            return NOT_FOUND

        course = courses[0]
        return {
            "id": course.get("id"),
            "fullname": course.get("fullname", ""),
            "shortname": course.get("shortname", ""),
            "url": f"{self._base_url}/course/view.php?id={course.get('id')}",
        }

    def get_course_contents(self, course_id: int) -> list[dict] | _NotFound:
        """
        Ambil struktur section dan module dari sebuah course.

        Return:
          - list of section dicts jika berhasil
          - NOT_FOUND jika course tidak ditemukan
          - Raise MoodleAPIError jika error fatal
        """
        logger.debug("get_course_contents: course_id=%d", course_id)

        result = self._request(
            "core_course_get_contents",
            {"courseid": course_id},
        )

        if isinstance(result, _NotFound):
            return NOT_FOUND

        if not isinstance(result, list):
            logger.warning(
                "get_course_contents: response tidak berupa list (course_id=%d): %s",
                course_id, type(result),
            )
            return NOT_FOUND

        return result


    def close(self) -> None:
        """Tutup HTTP session."""
        self._session.close()

    def __enter__(self) -> "MoodleClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
