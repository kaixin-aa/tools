"""Command line interface for word-to-pdf."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from .backends import ConversionBackend, choose_backend
from .converter import (
    convert_directory,
    validate_report_paths,
    write_reports,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="word-to-pdf",
        description="Recursively convert Word documents to PDFs without changing the source.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    convert = subparsers.add_parser(
        "convert",
        help="Convert supported Word documents in a directory.",
    )
    convert.add_argument("input", type=Path, help="Directory containing Word documents.")
    convert.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Empty or absent directory that will contain only generated PDFs.",
    )
    convert.add_argument(
        "--report",
        required=True,
        type=Path,
        help="JSON report path. A Markdown summary is written next to it by default.",
    )
    convert.add_argument(
        "--markdown-report",
        type=Path,
        help="Optional Markdown report path. Defaults to REPORT with a .md suffix.",
    )
    convert.add_argument(
        "--backend",
        choices=("auto", "word", "libreoffice"),
        default="auto",
        help="Rendering backend. Auto prefers Microsoft Word, then LibreOffice.",
    )
    return parser


def run(
    args: argparse.Namespace,
    stdout: TextIO,
    stderr: TextIO,
    backend: ConversionBackend | None = None,
) -> int:
    """Run a parsed CLI command."""

    if args.command != "convert":
        raise ValueError(f"unknown command: {args.command}")
    markdown_report = args.markdown_report or args.report.with_suffix(".md")
    validate_report_paths(args.input, args.output, args.report, markdown_report)
    selected_backend = backend or choose_backend(args.backend)
    report = convert_directory(args.input, args.output, selected_backend)
    write_reports(report, args.report, markdown_report)

    summary = report.summary
    stdout.write(
        f"conversion complete with {selected_backend.name}: "
        f"{summary['converted']} converted, {summary['failed']} failed, "
        f"{summary['skipped']} skipped.\n"
        f"PDF directory: {args.output}\n"
        f"JSON report: {args.report}\n"
        f"Markdown report: {markdown_report}\n"
    )
    if summary["failed"]:
        stderr.write("Some documents failed to convert. Review the report.\n")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, sys.stdout, sys.stderr)
    except Exception as exc:  # pragma: no cover - exercised by command-line use.
        parser.exit(1, f"word-to-pdf: error: {exc}\n")
