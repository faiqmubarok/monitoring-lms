"""
content_checker.py
Phase 3 + 4: Parser section → P1–P14 dan detektor PPT / Video / Quiz.

Mapping:
  Prioritas 1: nama section mengandung "Pertemuan N" → mapped ke P-N
  Prioritas 2: nomor urut section (fallback untuk course tanpa label Pertemuan)
  Section 0 (General), UTS, UAS → diabaikan

Detektor:
  PPT  : mimetype pptx, ekstensi .ppt/.pptx, Google Slides URL, keyword nama
  Video: modname video, mimetype video/*, ekstensi video, Google Drive file URL, keyword nama
  Quiz : modname == 'quiz'
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.moodle_api import MoodleClient, MoodleAPIError, NOT_FOUND

logger = logging.getLogger(__name__)

# ── Konstanta ─────────────────────────────────────────────────────────────────
MIN_PERTEMUAN = 1
MAX_PERTEMUAN = 14


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class MeetingContent:
    """Konten untuk satu pertemuan (P1–P14)."""
    pertemuan: int          # 1..14
    section_name: str       # nama section di Moodle (misal "3 October - 9 October")
    has_ppt: bool = False
    has_video: bool = False
    has_quiz: bool = False
    quiz_instance_id: int | None = None          # instance ID quiz untuk API lookup
    modules_raw: list[dict] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.has_ppt and self.has_video and self.has_quiz

    @property
    def missing(self) -> list[str]:
        """Daftar konten yang belum ada."""
        result = []
        if not self.has_ppt:
            result.append("PPT")
        if not self.has_video:
            result.append("Video")
        if not self.has_quiz:
            result.append("Quiz")
        return result

    @property
    def label(self) -> str:
        """Label ringkas untuk kolom P1–P14 di report."""
        if self.is_complete:
            return "LENGKAP"
        if not self.modules_raw:
            return ", ".join(self.missing)
        return ", ".join(self.missing)


@dataclass
class CourseCheckResult:
    """Hasil pengecekan satu course."""
    course_id: int
    meetings: dict[int, MeetingContent] = field(default_factory=dict)  # {1: M1, ..., 14: M14}
    error: str | None = None

    @property
    def overall_status(self) -> str:
        """
        LENGKAP            : semua P1–P14 ada PPT+Video+Quiz
        BELUM LENGKAP      : course ditemukan tapi ada yang kurang
        """
        if self.error:
            return "ERROR"
        if not self.meetings:
            return "BELUM LENGKAP"
        if all(m.is_complete for m in self.meetings.values()):
            return "LENGKAP"
        return "BELUM LENGKAP"

    @property
    def detail_kekurangan(self) -> str:
        """
        Format: "P2: Video, Quiz | P4: PPT | P7: PPT, Video, Quiz"
        Jika semua lengkap: "-"
        """
        parts = []
        for p_num in sorted(self.meetings.keys()):
            m = self.meetings[p_num]
            if not m.is_complete:
                parts.append(f"P{p_num}: {', '.join(m.missing)}")
        return " | ".join(parts) if parts else "-"


# ── PPT Detector ─────────────────────────────────────────────────────────────

_PPT_EXTENSIONS = {".ppt", ".pptx"}
# Hanya kata yang benar-benar spesifik ke PPT/slide
# 'materi' dan 'presentasi' dihapus karena terlalu ambigu
_PPT_KEYWORDS = re.compile(
    r"\b(ppt|powerpoint|slide)\b", re.IGNORECASE
)
_PPT_MIMETYPES = {
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
# Google Slides URL pattern
_GOOGLE_SLIDES_URL = re.compile(
    r"docs\.google\.com/presentation", re.IGNORECASE
)


def detect_ppt(module: dict) -> bool:
    """
    Deteksi PPT/slide presentasi.
    Prioritas: mimetype → ekstensi → Google Slides URL → keyword nama modul.
    Keyword fallback HANYA untuk kata yang benar-benar spesifik (ppt, powerpoint, slide).
    """
    modname = module.get("modname", "").lower()
    module_name = module.get("name", "")

    contents = module.get("contents", [])
    for content in contents:
        mimetype = content.get("mimetype", "").lower()
        filename = content.get("filename", "").lower()
        fileurl  = content.get("fileurl", "")

        if mimetype in _PPT_MIMETYPES:
            return True
        for ext in _PPT_EXTENSIONS:
            if filename.endswith(ext) or fileurl.lower().endswith(ext):
                return True
        # Google Slides link (dosen upload lewat URL activity)
        if fileurl and _GOOGLE_SLIDES_URL.search(fileurl):
            return True

    # Untuk modname=url atau resource (dosen share link langsung)
    module_url = module.get("url", "")
    if modname in ("url", "resource") and module_url:
        if _GOOGLE_SLIDES_URL.search(module_url):
            return True

    # Fallback: keyword KETAT di nama modul (hanya ppt/powerpoint/slide)
    if _PPT_KEYWORDS.search(module_name):
        return True

    return False


# ── Video Detector ────────────────────────────────────────────────────────────

_VIDEO_MODNAMES = {"videotime", "hvp", "mediagallery"}
_VIDEO_MIMETYPES = re.compile(r"^video/")
_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv"}
# Keyword 'video' di nama modul DIHAPUS sebagai fallback — terlalu longgar.
# Nama modul saja bukan bukti bahwa konten video benar-benar ada.
_VIDEO_PLATFORMS = re.compile(
    r"(youtube\.com|youtu\.be|vimeo\.com)", re.IGNORECASE
)
# Google Drive file link (bukan Slides) — untuk video yang diupload ke Drive
_GOOGLE_DRIVE_FILE = re.compile(
    r"drive\.google\.com/(file/|open\?)", re.IGNORECASE
)


def detect_video(module: dict) -> bool:
    """
    Deteksi video.
    Prioritas: modname khusus → mimetype → ekstensi → platform video URL
               → Google Drive file URL.
    TIDAK menggunakan keyword nama modul sebagai fallback (terlalu longgar).
    """
    modname = module.get("modname", "").lower()

    # Modul khusus video
    if modname in _VIDEO_MODNAMES:
        return True

    contents = module.get("contents", [])
    for content in contents:
        mimetype = content.get("mimetype", "").lower()
        filename = content.get("filename", "").lower()
        fileurl  = content.get("fileurl", "")

        if _VIDEO_MIMETYPES.match(mimetype):
            return True
        for ext in _VIDEO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        if fileurl and (_VIDEO_PLATFORMS.search(fileurl) or _GOOGLE_DRIVE_FILE.search(fileurl)):
            return True

    # URL/resource module — cek url di level module juga
    if modname in ("url", "resource"):
        module_url = module.get("url", "")
        if module_url and (
            _VIDEO_PLATFORMS.search(module_url)
            or _GOOGLE_DRIVE_FILE.search(module_url)
        ):
            return True

    # Tidak ada keyword fallback — deteksi hanya berdasarkan konten nyata
    return False


# ── Quiz Detector ─────────────────────────────────────────────────────────────

def detect_quiz(module: dict) -> bool:
    """
    Quiz tersedia jika modname == 'quiz'.
    Ini berdasarkan konfirmasi dari Moodle USI (section 29 spec).
    """
    return module.get("modname", "").lower() == "quiz"


# ── Section Parser ────────────────────────────────────────────────────────────

# Pattern untuk mendeteksi "Pertemuan N" di nama section (case-insensitive)
_PERTEMUAN_PATTERN = re.compile(r"pertemuan\s*(\d+)", re.IGNORECASE)

# Nama section yang harus diabaikan
_IGNORED_SECTION_NAMES = re.compile(
    r"\b(general|uts|uas|ujian|remedial|pengumuman|announcements)\b",
    re.IGNORECASE,
)


def _section_to_pertemuan(section: dict) -> int | None:
    """
    Tentukan nomor pertemuan (1–14) dari satu section dict.

    Strategi:
    1. Cari pola "Pertemuan N" di nama section → pakai N
    2. Jika nama mengandung kata UTS/UAS/General/dll → skip (return None)
    3. Fallback: pakai nomor section jika 1–14

    Return None = section ini tidak diperhitungkan sebagai Pertemuan 1-14.
    """
    name = section.get("name", "")
    num  = section.get("section", -1)

    # Skip section 0 (General) selalu
    if num == 0:
        return None

    # Cek nama explicit "Pertemuan N"
    m = _PERTEMUAN_PATTERN.search(name)
    if m:
        p = int(m.group(1))
        if MIN_PERTEMUAN <= p <= MAX_PERTEMUAN:
            return p
        return None  # "Pertemuan 15" dst — di luar range

    # Skip section yang namanya jelas bukan pertemuan kuliah
    if _IGNORED_SECTION_NAMES.search(name):
        return None

    # Fallback: nomor section sebagai pertemuan (untuk course tanpa label Pertemuan)
    if MIN_PERTEMUAN <= num <= MAX_PERTEMUAN:
        return num

    return None


def parse_sections(sections_raw: list[dict]) -> dict[int, MeetingContent]:
    """
    Parse raw section list dari core_course_get_contents.

    Mapping dilakukan via _section_to_pertemuan():
      - Nama "Pertemuan N" → prioritas utama
      - UTS/UAS/General → diabaikan
      - Fallback ke nomor section jika tidak ada label "Pertemuan"

    Return: {pertemuan_number: MeetingContent}
    """
    meetings: dict[int, MeetingContent] = {}

    for section in sections_raw:
        pertemuan = _section_to_pertemuan(section)
        if pertemuan is None:
            continue

        # Jika dua section map ke pertemuan yang sama, skip duplikat
        if pertemuan in meetings:
            logger.warning(
                "Duplikat mapping P%d: '%s' vs '%s' — pakai yang pertama",
                pertemuan, meetings[pertemuan].section_name, section.get("name"),
            )
            continue

        section_name = section.get("name", f"Section {section.get('section')}")
        modules = section.get("modules", [])

        meeting = MeetingContent(
            pertemuan=pertemuan,
            section_name=section_name,
            modules_raw=modules,
        )

        for module in modules:
            if not meeting.has_ppt and detect_ppt(module):
                meeting.has_ppt = True
                logger.debug("P%d PPT: %s", pertemuan, module.get("name"))
            if not meeting.has_video and detect_video(module):
                meeting.has_video = True
                logger.debug("P%d Video: %s", pertemuan, module.get("name"))
            if not meeting.has_quiz and detect_quiz(module):
                meeting.has_quiz = True
                meeting.quiz_instance_id = module.get("instance")  # untuk API lookup jadwal
                logger.debug("P%d Quiz: %s (instance=%s)", pertemuan, module.get("name"), meeting.quiz_instance_id)

        meetings[pertemuan] = meeting

    # Pastikan semua P1–P14 ada meski section tidak ada di Moodle
    for p in range(MIN_PERTEMUAN, MAX_PERTEMUAN + 1):
        if p not in meetings:
            meetings[p] = MeetingContent(pertemuan=p, section_name="(tidak ada)")

    return meetings


# ── Main check function ───────────────────────────────────────────────────────

def check_course_content(
    course_id: int,
    client: MoodleClient,
) -> CourseCheckResult:
    """
    Ambil konten course dan cek P1–P14.

    Return: CourseCheckResult
    """
    result = CourseCheckResult(course_id=course_id)

    try:
        sections_raw = client.get_course_contents(course_id)

        if isinstance(sections_raw, type(NOT_FOUND)):
            result.error = "COURSE TIDAK DITEMUKAN saat get_contents"
            return result

        result.meetings = parse_sections(sections_raw)

    except MoodleAPIError as exc:
        result.error = str(exc)
        logger.error("Error check course %d: %s", course_id, exc)

    return result
