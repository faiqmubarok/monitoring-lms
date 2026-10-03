#!/usr/bin/env python3
"""
main.py
Entry point CLI untuk USI Moodle LMS Checker.

Penggunaan:
    python main.py resource/SIP.xlsx
    python main.py resource/SIP.xlsx --full-refresh
    python main.py resource/SIP.xlsx --output output/report_custom.xlsx
"""

import argparse
import logging
import sys
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="USI Moodle LMS Content Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python main.py resource/SIP.xlsx
  python main.py resource/SIP.xlsx --full-refresh
  python main.py resource/SIP.xlsx --output output/laporan.xlsx
  python main.py resource/SIP.xlsx --verbose
        """,
    )
    parser.add_argument(
        "excel_path",
        help="Path ke file Excel KRS dari SIP (contoh: resource/SIP.xlsx)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path output file Excel report (default: output/report_YYYYMMDD_HHMMSS.xlsx)",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        default=False,
        help="Abaikan cache, ambil ulang semua data dari Moodle API",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Tampilkan log debug",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    excel_path = Path(args.excel_path)
    if not excel_path.exists():
        print(f"❌ File tidak ditemukan: {excel_path}")
        sys.exit(1)

    # Import di sini agar logging sudah di-setup dulu
    from src.orchestrator import run

    try:
        summary = run(
            excel_path=excel_path,
            output_path=args.output,
            full_refresh=args.full_refresh,
        )
        if not summary:
            sys.exit(1)
    except EnvironmentError as exc:
        print(f"\n❌ Konfigurasi error: {exc}")
        print("   Pastikan file .env sudah dibuat dari .env.example dan MOODLE_TOKEN sudah diisi.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠  Dihentikan oleh user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
