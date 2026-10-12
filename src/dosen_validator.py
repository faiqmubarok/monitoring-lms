"""
dosen_validator.py
Validasi kesesuaian nama dosen antara Excel dan Moodle course fullname.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Pattern untuk gelar akademik (S., M., Dr., Ir., dll.)
_GELAR_PATTERN = re.compile(
    r"\b(S\.|M\.|Dr\.|Ir\.|Prof\.|Drs\.|Dra\.|[A-Z]{2,5}\.)",
    re.IGNORECASE
)


def extract_dosen_names(dosen_str: str) -> list[str]:
    """
    Extract nama-nama dosen dari string Excel (bisa ada multiple dosen dipisah "|").
    
    Contoh input:
      - "Damara Astiningtyas, S.Kom., M.Kom."
      - "- Adhisty Triandini, S.Psi., M.Psi., Psikolog"
      - "Ali Muhammad, S.Kom | Budi Santoso, S.T."
      - "Dr. Umban Adi Jaya, S.Pd.,M.M"
    
    Return: list nama inti (minimal 2 kata) tanpa gelar, contoh:
      ["Damara Astiningtyas", "Ali Muhammad", "Budi Santoso"]
    """
    if not dosen_str or not dosen_str.strip():
        return []
    
    # Split by "|" untuk multiple dosen
    dosen_list = [d.strip() for d in dosen_str.split("|")]
    
    result = []
    for dosen_raw in dosen_list:
        # Hapus prefix dash dan strip
        dosen = dosen_raw.strip().lstrip("-").strip()
        
        # Hapus semua gelar akademik (S., M., Dr., dll.)
        dosen_no_gelar = _GELAR_PATTERN.sub("", dosen)
        
        # Hapus koma, strip whitespace berlebih
        dosen_clean = re.sub(r"[,.]", " ", dosen_no_gelar)
        dosen_clean = re.sub(r"\s+", " ", dosen_clean).strip()
        
        # Ambil minimal 2 kata pertama (nama depan + nama belakang)
        words = dosen_clean.split()
        if len(words) >= 2:
            # Ambil 2 kata pertama untuk avoid false positive (misal "Ade" saja)
            nama_inti = " ".join(words[:2])
            result.append(nama_inti)
        elif len(words) == 1:
            # Edge case: nama 1 kata (jarang, tapi ada seperti "Probokusumo")
            result.append(words[0])
    
    return result


def validate_dosen_match(
    dosen_excel: str,
    course_fullname: str,
) -> bool:
    """
    Validasi apakah nama dosen dari Excel ada di course fullname Moodle.
    
    Args:
      dosen_excel: nama dosen dari Excel (bisa multiple dipisah "|")
      course_fullname: fullname course dari Moodle
    
    Return:
      True jika minimal 1 nama dosen match (case-insensitive)
      False jika tidak ada yang match
    
    Example:
      Excel: "Damara Astiningtyas, S.Kom., M.Kom."
      Moodle: "Pengantar TI - 13FA (Damara Astiningtyas,)"
      → True
      
      Excel: "Ali Muhammad, S.Kom | Budi Santoso, S.T."
      Moodle: "Database - 23FA (Ali Muhammad,)"
      → True (salah satu match)
    """
    if not dosen_excel or not course_fullname:
        return False
    
    # Extract nama inti dari Excel
    dosen_names = extract_dosen_names(dosen_excel)
    if not dosen_names:
        return False
    
    # Normalize course fullname untuk comparison
    fullname_lower = course_fullname.lower()
    
    # Cek apakah salah satu nama ada di fullname
    for nama in dosen_names:
        if nama.lower() in fullname_lower:
            logger.debug(
                "Dosen match: '%s' found in '%s'",
                nama, course_fullname
            )
            return True
    
    logger.debug(
        "Dosen NOT match: %s not found in '%s'",
        dosen_names, course_fullname
    )
    return False


def get_dosen_status(
    dosen_excel: str,
    course_fullname: str | None,
    course_found: bool,
) -> str:
    """
    Return status dosen untuk Excel report.
    
    Return:
      "✅" - dosen sesuai
      "❌" - dosen tidak sesuai
      "N/A" - course tidak ditemukan
    """
    if not course_found or not course_fullname:
        return "N/A"
    
    if validate_dosen_match(dosen_excel, course_fullname):
        return "✅"
    else:
        return "❌"
