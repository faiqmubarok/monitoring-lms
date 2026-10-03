"""
test_phase2.py
Test PHASE 2–4: Moodle API client + course lookup + content check.

Menguji:
  1. Koneksi ke Moodle API
  2. get_course_by_shortname (ditemukan & tidak ditemukan)
  3. get_course_contents
  4. parse_sections → P1–P14
  5. detect_ppt / detect_video / detect_quiz
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_phase2")
sys.path.insert(0, str(Path(__file__).parent))

from src.moodle_api import MoodleClient, MoodleAPIError, NOT_FOUND
from src.content_checker import (
    parse_sections,
    detect_ppt,
    detect_video,
    detect_quiz,
    check_course_content,
    MIN_PERTEMUAN,
    MAX_PERTEMUAN,
)
from src import config

tests_passed = 0
tests_failed = 0

def assert_test(name: str, condition: bool, detail: str = "") -> None:
    global tests_passed, tests_failed
    if condition:
        print(f"  ✅ PASS: {name}")
        tests_passed += 1
    else:
        print(f"  ❌ FAIL: {name} {detail}")
        tests_failed += 1


# ── Unit tests detektor (tidak perlu koneksi) ─────────────────────────────────
def test_detectors() -> None:
    print("\n" + "=" * 70)
    print("  Unit Tests: PPT / Video / Quiz Detector")
    print("=" * 70)

    # PPT — via mimetype
    assert_test(
        "detect_ppt via mimetype pptx",
        detect_ppt({
            "modname": "resource",
            "name": "Materi Pertemuan 1",
            "contents": [{
                "mimetype": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "filename": "materi.pptx",
                "fileurl": "https://lms2.sains.ac.id/pluginfile.php/123/materi.pptx",
            }],
        }),
    )

    # PPT — via ekstensi .ppt
    assert_test(
        "detect_ppt via ekstensi .ppt",
        detect_ppt({
            "modname": "resource",
            "name": "Slide",
            "contents": [{"mimetype": "application/octet-stream", "filename": "slide.ppt", "fileurl": ""}],
        }),
    )

    # PPT — via keyword nama modul
    assert_test(
        "detect_ppt via keyword 'Materi'",
        detect_ppt({"modname": "resource", "name": "Materi Kuliah Week 1", "contents": []}),
    )

    # PPT — tidak terdeteksi untuk file PDF
    assert_test(
        "detect_ppt TIDAK mendeteksi PDF",
        not detect_ppt({
            "modname": "resource",
            "name": "Handout",
            "contents": [{"mimetype": "application/pdf", "filename": "handout.pdf", "fileurl": ""}],
        }),
    )

    # Video — via modname videotime
    assert_test(
        "detect_video via modname 'videotime'",
        detect_video({"modname": "videotime", "name": "Video Kuliah", "contents": []}),
    )

    # Video — via YouTube URL
    assert_test(
        "detect_video via YouTube URL",
        detect_video({
            "modname": "url",
            "name": "Tonton Video",
            "contents": [{"fileurl": "https://www.youtube.com/watch?v=abc123", "filename": "", "mimetype": ""}],
        }),
    )

    # Video — via keyword nama
    assert_test(
        "detect_video via keyword 'Video'",
        detect_video({"modname": "resource", "name": "Video Pembelajaran", "contents": []}),
    )

    # Video — tidak terdeteksi untuk Word doc
    assert_test(
        "detect_video TIDAK mendeteksi Word doc",
        not detect_video({
            "modname": "resource",
            "name": "Handout Word",
            "contents": [{"mimetype": "application/msword", "filename": "handout.doc", "fileurl": ""}],
        }),
    )

    # Quiz — via modname quiz
    assert_test(
        "detect_quiz via modname 'quiz'",
        detect_quiz({"modname": "quiz", "name": "Quiz Pertemuan 1", "contents": []}),
    )

    # Quiz — tidak terdeteksi untuk forum
    assert_test(
        "detect_quiz TIDAK mendeteksi forum",
        not detect_quiz({"modname": "forum", "name": "Diskusi", "contents": []}),
    )


def test_parse_sections_empty() -> None:
    print("\n" + "=" * 70)
    print("  Unit Tests: parse_sections (data mock)")
    print("=" * 70)

    # Mock section list seperti response Moodle USI
    mock_sections = [
        {
            "section": 0,
            "name": "General",
            "modules": [{"modname": "forum", "name": "Announcements", "contents": []}],
        },
        {
            "section": 1,
            "name": "3 October - 9 October",
            "modules": [
                {
                    "modname": "resource",
                    "name": "PPT Pertemuan 1",
                    "contents": [{"mimetype": "application/vnd.ms-powerpoint", "filename": "p1.ppt", "fileurl": ""}],
                },
                {
                    "modname": "url",
                    "name": "Video Kuliah 1",
                    "contents": [{"fileurl": "https://youtu.be/abc", "filename": "", "mimetype": ""}],
                },
                {"modname": "quiz", "name": "Quiz 1", "contents": []},
            ],
        },
        {
            "section": 2,
            "name": "10 October - 16 October",
            "modules": [],  # kosong
        },
        {
            "section": 15,
            "name": "Extra Section",
            "modules": [{"modname": "forum", "name": "Diskusi Akhir", "contents": []}],
        },
    ]

    meetings = parse_sections(mock_sections)

    assert_test("parse_sections menghasilkan 14 pertemuan", len(meetings) == 14)
    assert_test("P1 has_ppt = True", meetings[1].has_ppt)
    assert_test("P1 has_video = True", meetings[1].has_video)
    assert_test("P1 has_quiz = True", meetings[1].has_quiz)
    assert_test("P1 is_complete = True", meetings[1].is_complete)
    assert_test("P1 label = LENGKAP", meetings[1].label == "LENGKAP")
    assert_test("P2 kosong (missing 3 konten)", len(meetings[2].missing) == 3)
    assert_test("P2 label = PPT, Video, Quiz", meetings[2].label == "PPT, Video, Quiz")
    assert_test("Section 0 diabaikan (tidak ada P0)", 0 not in meetings)
    assert_test("Section 15 diabaikan (tidak ada P15)", 15 not in meetings)


def test_moodle_api() -> None:
    print("\n" + "=" * 70)
    print("  Live Tests: Moodle API")
    print(f"  URL: {config.MOODLE_URL}")
    print("=" * 70)

    try:
        with MoodleClient() as client:

            # Test 1: shortname yang tidak ada
            print("\n  [1] Test shortname tidak ada...")
            result_notfound = client.get_course_by_shortname("SHORTNAME_PASTI_TIDAK_ADA_99999")
            assert_test(
                "get_course_by_shortname → NOT_FOUND untuk shortname tidak ada",
                isinstance(result_notfound, type(NOT_FOUND)),
                f"(got: {result_notfound})",
            )

            # Test 2: shortname yang ada (dari issue.md: 26FA_Psikologi Komunikasi_20261)
            print("\n  [2] Test shortname yang diketahui ada (dari issue.md)...")
            known_shortname = "26FA_Psikologi Komunikasi_20261"
            result_found = client.get_course_by_shortname(known_shortname)

            if isinstance(result_found, type(NOT_FOUND)):
                print(f"  ⚠  Course '{known_shortname}' tidak ditemukan di server.")
                print("     Mungkin kelas ini sudah tidak ada. Lanjut ke test berikutnya.")
            else:
                assert_test(
                    "get_course_by_shortname → dict dengan course_id",
                    isinstance(result_found, dict) and "id" in result_found,
                    f"(got: {result_found})",
                )
                print(f"     Course ditemukan: id={result_found['id']}, fullname={result_found['fullname']}")
                course_id = result_found["id"]

                # Test 3: get_course_contents
                print(f"\n  [3] Test get_course_contents untuk course id={course_id}...")
                sections = client.get_course_contents(course_id)

                assert_test(
                    "get_course_contents → list",
                    isinstance(sections, list),
                    f"(got type: {type(sections)})",
                )

                if isinstance(sections, list):
                    print(f"     Total sections: {len(sections)}")
                    for s in sections[:5]:
                        print(f"       section {s.get('section')}: {s.get('name')} | modules: {len(s.get('modules', []))}")

                    # Test 4: parse sections
                    meetings = parse_sections(sections)
                    assert_test(
                        "parse_sections menghasilkan 14 meetings",
                        len(meetings) == MAX_PERTEMUAN,
                        f"(got: {len(meetings)})",
                    )

                    # Test 5: full check_course_content
                    print(f"\n  [4] Test check_course_content untuk course id={course_id}...")
                    check_result = check_course_content(course_id, client)

                    assert_test(
                        "check_course_content tidak error",
                        check_result.error is None,
                        f"(error: {check_result.error})",
                    )

                    print(f"\n     Status keseluruhan: {check_result.overall_status}")
                    print(f"     Detail kekurangan : {check_result.detail_kekurangan}")
                    print()
                    for p in range(1, MAX_PERTEMUAN + 1):
                        m = check_result.meetings.get(p)
                        if m:
                            ppt = "✅" if m.has_ppt else "❌"
                            vid = "✅" if m.has_video else "❌"
                            quz = "✅" if m.has_quiz else "❌"
                            print(f"     P{p:2d}: PPT{ppt} Video{vid} Quiz{quz} | {m.section_name[:40]}")

    except MoodleAPIError as exc:
        print(f"\n  ❌ FATAL: Tidak bisa konek ke Moodle API: {exc}")
        print("     Pastikan MOODLE_URL dan MOODLE_TOKEN sudah benar di file .env")
        tests_failed + 1


if __name__ == "__main__":
    # Unit tests (offline)
    test_detectors()
    test_parse_sections_empty()

    # Live API tests
    test_moodle_api()

    print("\n" + "=" * 70)
    print(f"  Total: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)

    if tests_failed > 0:
        sys.exit(1)

    print("\n✅ PHASE 2-4 SELESAI\n")
