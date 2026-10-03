"""
test_phase5_8.py
Test Phase 5-8: Report generator + orchestrator end-to-end dengan data sampel kecil.

Test:
  1. generate_report dengan mock data → cek file xlsx terbuat
  2. run orchestrator dengan 5 kelas nyata dari Excel
  3. Cek struktur output file
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
sys.path.insert(0, str(Path(__file__).parent))

import openpyxl

from src.content_checker import MeetingContent, MIN_PERTEMUAN, MAX_PERTEMUAN
from src.report_generator import generate_report
from src.excel_reader import read_and_filter

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


def _make_mock_meetings(has_ppt=True, has_video=True, has_quiz=True) -> dict:
    meetings = {}
    for p in range(MIN_PERTEMUAN, MAX_PERTEMUAN + 1):
        meetings[p] = MeetingContent(
            pertemuan=p,
            section_name=f"Section {p}",
            has_ppt=has_ppt,
            has_video=has_video,
            has_quiz=has_quiz,
        )
    return meetings


def test_report_generator():
    print("\n" + "=" * 70)
    print("  Test: Report Generator (mock data)")
    print("=" * 70)

    mock_results = [
        {
            "kode_kelas": "36BA",
            "matakuliah": "HKM305 - Hukum Administrasi Negara",
            "sks": "3", "smt": "3",
            "jadwal": "Sabtu09:10:00-11:10:00",
            "dosen": "Dr. Syaiful Bahari, S.H.,M.H",
            "prodi": "S1 Hukum",
            "ruangan_kelas": "R2A",
            "kampus": "Kampus Cibitung",
            "identity_key": "36BA|HKM305|20261",
            "moodle_shortname": "36BA_HKM305 - Hukum Administrasi Negara_20261",
            "match_status": "DITEMUKAN",
            "lms_status": "LENGKAP",
            "course_id": 100,
            "course_fullname": "Hukum Administrasi Negara - 36BA",
            "course_shortname": "36BA_HKM305_20261",
            "course_url": "https://lms2.sains.ac.id/course/view.php?id=100",
            "match_error": None,
            "meetings": _make_mock_meetings(True, True, True),
            "detail_kekurangan": "-",
            "last_check": "26/09/2026 21:00:00",
        },
        {
            "kode_kelas": "46EA",
            "matakuliah": "INF405 - Internet of Things",
            "sks": "3", "smt": "4",
            "jadwal": "Sabtu16:40:00-18:40:00",
            "dosen": "Achmad Chotib, S.Kom., M.Kom.",
            "prodi": "S1 Teknik Informatika",
            "ruangan_kelas": "R2B",
            "kampus": "Kampus Cibitung",
            "identity_key": "46EA|INF405|20261",
            "moodle_shortname": "46EA_INF405 - Internet of Things_20261",
            "match_status": "DITEMUKAN",
            "lms_status": "BELUM LENGKAP",
            "course_id": 101,
            "course_fullname": "IoT - 46EA",
            "course_shortname": "46EA_INF405_20261",
            "course_url": "https://lms2.sains.ac.id/course/view.php?id=101",
            "match_error": None,
            "meetings": _make_mock_meetings(True, False, False),
            "detail_kekurangan": "P1: Video, Quiz | P2: Video, Quiz | P3: Video, Quiz",
            "last_check": "26/09/2026 21:00:00",
        },
        {
            "kode_kelas": "56CA",
            "matakuliah": "PSI504 - Observasi & Wawancara",
            "sks": "3", "smt": "5",
            "jadwal": "Sabtu11:20:00-13:20:00",
            "dosen": "",
            "prodi": "S1 Psikologi",
            "ruangan_kelas": "R2C",
            "kampus": "Kampus Cibitung",
            "identity_key": "56CA|PSI504|20261",
            "moodle_shortname": "56CA_PSI504 - Observasi & Wawancara_20261",
            "match_status": "BELUM KRS",
            "lms_status": "BELUM KRS",
            "course_id": None,
            "course_fullname": None,
            "course_shortname": None,
            "course_url": None,
            "match_error": None,
            "meetings": {},
            "detail_kekurangan": "-",
            "last_check": "26/09/2026 21:00:00",
        },
        {
            "kode_kelas": "16DA",
            "matakuliah": "FIT101 - Kalkulus 1",
            "sks": "3", "smt": "1",
            "jadwal": "Sabtu14:30:00-16:30:00",
            "dosen": "Probokusumo, ST., MT.",
            "prodi": "S1 Teknik Industri",
            "ruangan_kelas": "R2B",
            "kampus": "Kampus Tambun",
            "identity_key": "16DA|FIT101|20261",
            "moodle_shortname": "16DA_FIT101 - Kalkulus 1_20261",
            "match_status": "COURSE TIDAK DITEMUKAN",
            "lms_status": "COURSE TIDAK DITEMUKAN",
            "course_id": None,
            "course_fullname": None,
            "course_shortname": None,
            "course_url": None,
            "match_error": None,
            "meetings": {},
            "detail_kekurangan": "-",
            "last_check": "26/09/2026 21:00:00",
        },
    ]

    out_path = Path("output/test_report_mock.xlsx")
    report_path = generate_report(mock_results, output_path=out_path)

    assert_test("File report terbuat", report_path.exists())

    # Buka dan cek struktur
    wb = openpyxl.load_workbook(report_path)
    assert_test("Sheet DATA TERBARU ada", "DATA TERBARU" in wb.sheetnames)
    assert_test("Sheet RIWAYAT CEK ada", "RIWAYAT CEK" in wb.sheetnames)

    ws_data = wb["DATA TERBARU"]
    assert_test("DATA TERBARU punya header row", ws_data.cell(1, 1).value is not None)
    assert_test(
        "DATA TERBARU punya 4 baris data",
        ws_data.max_row == len(mock_results) + 1,
        f"(got: {ws_data.max_row})",
    )

    # Cek kolom header
    headers = [ws_data.cell(1, c).value for c in range(1, ws_data.max_column + 1)]
    assert_test("Header 'Kelas' ada", "Kelas" in headers)
    assert_test("Header 'P1' ada", "P1" in headers)
    assert_test("Header 'P14' ada", "P14" in headers)
    assert_test("Header 'Status LMS' ada", "Status LMS" in headers)
    assert_test("Header 'Detail Kekurangan' ada", "Detail Kekurangan" in headers)

    ws_riwayat = wb["RIWAYAT CEK"]
    assert_test(
        "RIWAYAT CEK minimal ada data",
        ws_riwayat.max_row >= 2,
        f"(rows: {ws_riwayat.max_row})",
    )

    wb.close()
    print(f"\n  📁 Mock report: {report_path}")

    # Test append histori (run kedua)
    report_path2 = generate_report(mock_results[:2], output_path=out_path)
    wb2 = openpyxl.load_workbook(report_path2)
    ws_riwayat2 = wb2["RIWAYAT CEK"]
    # Setelah run 2, riwayat harus lebih banyak dari run 1
    first_run_rows = ws_riwayat.max_row
    assert_test(
        "RIWAYAT CEK bertambah setelah run kedua",
        ws_riwayat2.max_row > first_run_rows,
        f"(before={first_run_rows}, after={ws_riwayat2.max_row})",
    )
    wb2.close()


def test_end_to_end_small():
    print("\n" + "=" * 70)
    print("  Test: End-to-End dengan 3 kelas nyata dari Excel")
    print("=" * 70)

    from src.orchestrator import run

    summary = run(
        excel_path=Path("resource/SIP.xlsx"),
        output_path=Path("output/test_report_live.xlsx"),
        full_refresh=False,
    )

    assert_test("Summary tidak kosong", bool(summary))
    assert_test("filtered_classes > 0", summary.get("filtered_classes", 0) > 0)
    assert_test("Report file ada", Path(summary.get("report_path", "")).exists())

    print(f"\n  📊 Summary: {summary}")


if __name__ == "__main__":
    test_report_generator()
    test_end_to_end_small()

    print("\n" + "=" * 70)
    print(f"  Total: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)

    if tests_failed > 0:
        sys.exit(1)
    print("\n✅ PHASE 5-8 SELESAI\n")
