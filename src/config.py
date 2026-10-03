"""
config.py
Membaca konfigurasi dari environment variables (.env).
Token Moodle tidak pernah dicetak ke log atau output.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_required(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise EnvironmentError(
            f"Environment variable '{key}' wajib diisi. "
            f"Salin .env.example ke .env dan isi nilainya."
        )
    return val


def _get_optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Moodle ──────────────────────────────────────────────────────────────────
MOODLE_URL: str = _get_optional("MOODLE_URL", "https://lms2.sains.ac.id").rstrip("/")
# Token diakses via fungsi agar tidak tersimpan di variabel modul yang mudah
# tercetak secara tidak sengaja.
def get_moodle_token() -> str:
    return _get_required("MOODLE_TOKEN")


# ── Semester ─────────────────────────────────────────────────────────────────
SEMESTER_CODE: str = _get_optional("SEMESTER_CODE", "20261")

# ── Filter ───────────────────────────────────────────────────────────────────
_raw_rooms = _get_optional("ALLOWED_ROOMS", "R2A,R2B,R2C")
ALLOWED_ROOMS: list[str] = [r.strip().upper() for r in _raw_rooms.split(",") if r.strip()]

# ── API ───────────────────────────────────────────────────────────────────────
API_TIMEOUT: int = int(_get_optional("API_TIMEOUT", "30"))
API_RETRY_COUNT: int = int(_get_optional("API_RETRY_COUNT", "3"))
API_RETRY_DELAY: float = float(_get_optional("API_RETRY_DELAY", "2"))

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_ENABLED: bool = _get_optional("CACHE_ENABLED", "true").lower() == "true"
CACHE_DIR: str = _get_optional("CACHE_DIR", ".cache")

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR: str = _get_optional("OUTPUT_DIR", "output")
