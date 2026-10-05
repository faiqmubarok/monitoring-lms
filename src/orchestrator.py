"""
orchestrator.py
Phase 8: Koordinator utama — menghubungkan semua komponen.

Alur:
  1. Baca & filter Excel
  2. Untuk setiap kelas:
     a. BELUM KRS → skip Moodle
     b. Ada dosen → lookup shortname (dengan cache)
     c. Course ditemukan → cek P1-P14 (dengan cache)
  3. Susun result dict lengkap
  4. Generate Excel report
  5. Simpan histori
  6. Tampilkan summary

Rate limiting: jeda kecil antar request agar tidak membebani Moodle.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from src.content_checker import check_course_content, parse_sections
from src.course_matcher import (
    STATUS_BELUM_KRS,
    STATUS_ERROR,
    STATUS_FOUND,
    STATUS_NOT_FOUND,
)
from src.excel_reader import (
    build_moodle_shortname,
    build_identity_key,
    read_and_filter,
)
from src.moodle_api import MoodleAPIError, MoodleClient, NOT_FOUND
from src.report_generator import generate_report
from src.quiz_schedule import parse_class_day, compute_expected_dates, validate_quiz_dates
from src import config

logger = logging.getLogger(__name__)
console = Console()

# Jeda antar request API (detik) — jaga Moodle tidak kelebihan beban
_API_RATE_DELAY = 0.3


def run(
    excel_path: str | Path,
    output_path: str | Path | None = None,
    full_refresh: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """
    Jalankan full check cycle.

    Args:
        excel_path   : path ke file Excel KRS terbaru
        output_path  : path output report (.xlsx), None = auto-generate
        full_refresh : parameter lama, diabaikan (tidak ada cache)
        on_progress  : callback(current, total, label) untuk UI kustom

    Return: summary dict
    """
    start_time = time.time()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    console.print(f"\n[bold cyan]🎓 USI Moodle LMS Checker[/bold cyan]")
    console.print(f"   Semester  : {config.SEMESTER_CODE}")
    console.print(f"   Moodle URL: {config.MOODLE_URL}")
    console.print(f"   Waktu     : {now_str}\n")

    # ── Step 1: Baca Excel ────────────────────────────────────────────────────
    console.print("[bold]Step 1:[/bold] Membaca file Excel...")
    filtered_rows, read_summary = read_and_filter(excel_path)

    console.print(
        f"   ✅ {read_summary['total_rows']} baris total | "
        f"[green]{read_summary['filtered']} lolos filter[/green] | "
        f"{read_summary['skipped_online']} skip online | "
        f"{read_summary['skipped_wrong_room']} skip ruangan lain\n"
    )

    if not filtered_rows:
        console.print("[yellow]⚠  Tidak ada kelas yang lolos filter.[/yellow]")
        return {}

    # ── Step 2: Proses setiap kelas ───────────────────────────────────────────
    console.print(f"[bold]Step 2:[/bold] Cek {len(filtered_rows)} kelas ke Moodle...\n")

    results: list[dict] = []

    # Counters
    cnt_belum_krs = 0
    cnt_not_found = 0
    cnt_found = 0
    cnt_lengkap = 0
    cnt_belum_lengkap = 0
    cnt_error = 0

    with MoodleClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            task = progress.add_task("Memproses kelas...", total=len(filtered_rows))

            for idx, row in enumerate(filtered_rows, start=1):
                kode = row.get("kode_kelas", "")
                mk = row.get("matakuliah", "")
                dosen = row.get("dosen", "").strip()
                semester = config.SEMESTER_CODE

                identity = build_identity_key(kode, mk, semester)
                shortname = build_moodle_shortname(kode, mk, semester)

                # Progress label
                label = f"{kode} | {mk[:35]}"
                progress.update(task, description=f"[cyan]{label:<50}[/cyan]")

                if on_progress:
                    on_progress(idx, len(filtered_rows), label)

                result = {
                    **row,
                    "identity_key": identity,
                    "moodle_shortname": shortname,
                    "match_status": None,
                    "lms_status": None,
                    "course_id": None,
                    "course_fullname": None,
                    "course_shortname": None,
                    "course_url": None,
                    "match_error": None,
                    "meetings": {},
                    "detail_kekurangan": "",
                    "quiz_jadwal_p1": None,   # None=tidak dicek, True=sesuai, False=salah
                    "last_check": now_str,
                }

                # ── BELUM KRS ─────────────────────────────────────────────────
                if not dosen:
                    result["match_status"] = STATUS_BELUM_KRS
                    result["lms_status"] = STATUS_BELUM_KRS
                    result["detail_kekurangan"] = "-"
                    cnt_belum_krs += 1
                    progress.advance(task)
                    results.append(result)
                    continue

                # ── Lookup course ─────────────────────────────────────────────
                try:
                    course = client.get_course_by_shortname(shortname)
                    time.sleep(_API_RATE_DELAY)

                    if course is None or isinstance(course, type(NOT_FOUND)):
                        result["match_status"] = STATUS_NOT_FOUND
                        result["lms_status"] = STATUS_NOT_FOUND
                        result["detail_kekurangan"] = "-"
                        cnt_not_found += 1
                        progress.advance(task)
                        results.append(result)
                        continue

                    result["match_status"] = STATUS_FOUND
                    result["course_id"] = course["id"]
                    result["course_fullname"] = course["fullname"]
                    result["course_shortname"] = course["shortname"]
                    result["course_url"] = course["url"]
                    cnt_found += 1

                    # ── Cek konten P1–P14 ─────────────────────────────────────
                    sections_raw = client.get_course_contents(course["id"])
                    time.sleep(_API_RATE_DELAY)

                    if sections_raw is None:
                        result["lms_status"] = STATUS_NOT_FOUND
                        result["detail_kekurangan"] = "-"
                    else:
                        meetings = parse_sections(sections_raw)
                        result["meetings"] = meetings

                        # Hitung status keseluruhan
                        if all(m.is_complete for m in meetings.values()):
                            result["lms_status"] = "LENGKAP"
                            cnt_lengkap += 1
                        else:
                            result["lms_status"] = "BELUM LENGKAP"
                            cnt_belum_lengkap += 1

                        # Detail kekurangan
                        parts = []
                        for p_num in sorted(meetings.keys()):
                            m = meetings[p_num]
                            if not m.is_complete:
                                parts.append(f"P{p_num}: {', '.join(m.missing)}")
                        result["detail_kekurangan"] = " | ".join(parts) if parts else "-"

                        # ── Validasi jadwal quiz P1 ───────────────────────────
                        p1 = meetings.get(1)
                        jadwal_str = row.get("jadwal", "")
                        class_day = parse_class_day(jadwal_str)

                        if (
                            p1 is not None
                            and p1.has_quiz
                            and p1.quiz_instance_id is not None
                            and class_day is not None
                            and config.SEMESTER_START_WEEK is not None
                        ):
                            quizzes = client.get_quizzes_by_course(course["id"])
                            time.sleep(_API_RATE_DELAY)

                            # Cari data quiz P1 berdasarkan instance ID
                            p1_quiz = next(
                                (q for q in quizzes if q.get("id") == p1.quiz_instance_id),
                                None,
                            )
                            if p1_quiz:
                                exp_open, exp_close = compute_expected_dates(
                                    class_day, 1, config.SEMESTER_START_WEEK
                                )
                                result["quiz_jadwal_p1"] = validate_quiz_dates(
                                    p1_quiz.get("timeopen"),
                                    p1_quiz.get("timeclose"),
                                    exp_open,
                                    exp_close,
                                )
                            else:
                                logger.debug(
                                    "Quiz instance %s tidak ditemukan di course %s",
                                    p1.quiz_instance_id, course["id"]
                                )

                except MoodleAPIError as exc:
                    result["match_status"] = STATUS_ERROR
                    result["lms_status"] = STATUS_ERROR
                    result["match_error"] = str(exc)
                    result["detail_kekurangan"] = f"API ERROR: {exc}"
                    cnt_error += 1
                    logger.error("Error kelas %s: %s", shortname, exc)

                progress.advance(task)
                results.append(result)

    # ── Step 3: Generate report ───────────────────────────────────────────────
    console.print("\n[bold]Step 3:[/bold] Membuat Excel report...")
    report_path = generate_report(results, output_path)
    console.print(f"   ✅ Report disimpan: [bold green]{report_path}[/bold green]\n")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    summary = {
        "total_excel_rows": read_summary["total_rows"],
        "filtered_classes": len(filtered_rows),
        "belum_krs": cnt_belum_krs,
        "course_found": cnt_found,
        "course_not_found": cnt_not_found,
        "lms_lengkap": cnt_lengkap,
        "lms_belum_lengkap": cnt_belum_lengkap,
        "errors": cnt_error,
        "elapsed_seconds": round(elapsed, 1),
        "report_path": str(report_path),
    }

    _print_summary(summary)
    return summary


def _print_summary(summary: dict) -> None:
    table = Table(
        title="📊 Hasil Pengecekan LMS",
        show_header=True,
        header_style="bold white on dark_blue",
    )
    table.add_column("Metrik", style="cyan", min_width=30)
    table.add_column("Jumlah", justify="right", style="bold white")

    rows = [
        ("Total baris Excel",        summary["total_excel_rows"]),
        ("Kelas setelah filter",      summary["filtered_classes"]),
        ("Belum KRS",                 summary["belum_krs"]),
        ("Course ditemukan",          summary["course_found"]),
        ("Course tidak ditemukan",    summary["course_not_found"]),
        ("LMS LENGKAP",               summary["lms_lengkap"]),
        ("LMS BELUM LENGKAP",         summary["lms_belum_lengkap"]),
        ("Error",                     summary["errors"]),
        ("Waktu proses (detik)",      summary["elapsed_seconds"]),
    ]

    for label, value in rows:
        table.add_row(label, str(value))

    console.print(table)
    console.print(f"\n📁 Report: [bold green]{summary['report_path']}[/bold green]\n")
