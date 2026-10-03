"""
test_phase1.py
Test PHASE 1: Excel reader + filter.

Jalankan dari root project:
    python test_phase1.py
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_phase1")

# Pastikan src/ ada di path
sys.path.insert(0, str(Path(__file__).parent))

from src.excel_reader import read_and_filter, build_identity_key, build_moodle_shortname

EXCEL_PATH = Path("resource/SIP.xlsx")
SEMESTER_CODE = "20261"


def test_filter():
    print("\n" + "=" * 70)
    print("  PHASE 1 TEST — Excel Reader & Filter")
    print("=" * 70)

    rows, summary = read_and_filter(EXCEL_PATH)

    print(f"\n📊 Statistik pembacaan:")
    print(f"   Total baris data     : {summary['total_rows']}")
    print(f"   Lolos filter         : {summary['filtered']}")
    print(f"   Skip (baris kosong)  : {summary['skipped_no_kode']}")
    print(f"   Skip (kelas online)  : {summary['skipped_online']}")
    print(f"   Skip (ruangan lain)  : {summary['skipped_wrong_room']}")

    print(f"\n📋 {len(rows)} kelas lolos filter:")
    print("-" * 70)

    for i, row in enumerate(rows, start=1):
        kode = row.get("kode_kelas", "-")
        mk = row.get("matakuliah", "-")
        dosen = row.get("dosen", "-") or "⚠ BELUM KRS"
        ruangan = row.get("ruangan_kelas", "-")
        kampus = row.get("kampus", "-")

        shortname = build_moodle_shortname(kode, mk, SEMESTER_CODE)
        identity = build_identity_key(kode, mk, SEMESTER_CODE)
        status_krs = "BELUM KRS" if not row.get("dosen", "").strip() else "ADA DOSEN"

        print(f"\n  [{i:3d}] {kode} | {ruangan} | {kampus}")
        print(f"        MK     : {mk}")
        print(f"        Dosen  : {dosen}")
        print(f"        Status : {status_krs}")
        print(f"        Shortname Moodle: {shortname}")
        print(f"        Identity Key    : {identity}")

    # ── Unit tests manual ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Unit Tests")
    print("=" * 70)

    tests_passed = 0
    tests_failed = 0

    def assert_test(name, condition, detail=""):
        nonlocal tests_passed, tests_failed
        if condition:
            print(f"  ✅ PASS: {name}")
            tests_passed += 1
        else:
            print(f"  ❌ FAIL: {name} {detail}")
            tests_failed += 1

    # Test build_shortname
    assert_test(
        "build_moodle_shortname",
        build_moodle_shortname("26FA", "Psikologi Komunikasi", "20261")
        == "26FA_Psikologi Komunikasi_20261",
    )

    # Test build_identity_key
    assert_test(
        "build_identity_key uppercase",
        build_identity_key("26fa", "Psikologi Komunikasi", "20261")
        == "26FA|Psikologi Komunikasi|20261",
    )

    # Test: tidak ada kelas online di hasil filter
    online_leaked = [r for r in rows if r.get("kode_kelas", "").endswith("O")]
    assert_test(
        "Tidak ada kelas online lolos filter",
        len(online_leaked) == 0,
        f"(ditemukan: {[r['kode_kelas'] for r in online_leaked]})",
    )

    # Test: semua ruangan adalah R2A/R2B/R2C
    from src.config import ALLOWED_ROOMS
    wrong_room = [r for r in rows if r.get("ruangan_kelas", "") not in ALLOWED_ROOMS]
    assert_test(
        "Semua ruangan adalah R2A/R2B/R2C",
        len(wrong_room) == 0,
        f"(ditemukan: {[(r['kode_kelas'], r['ruangan']) for r in wrong_room]})",
    )

    # Test: semua row punya kode_kelas
    no_kode = [r for r in rows if not r.get("kode_kelas")]
    assert_test(
        "Semua row memiliki kode_kelas",
        len(no_kode) == 0,
    )

    # Test: field dosen bisa kosong (BELUM KRS) → harus tetap ada di results
    belum_krs = [r for r in rows if not r.get("dosen", "").strip()]
    print(f"\n  ℹ  Kelas BELUM KRS (dosen kosong): {len(belum_krs)}")
    for r in belum_krs:
        print(f"       - {r['kode_kelas']} | {r.get('matakuliah', '-')}")

    print(f"\n  Total: {tests_passed} passed, {tests_failed} failed")
    print("=" * 70)

    if tests_failed > 0:
        sys.exit(1)

    print("\n✅ PHASE 1 SELESAI — Excel reader + filter berjalan dengan benar.\n")


if __name__ == "__main__":
    test_filter()
