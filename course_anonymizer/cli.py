"""Command line interface for course file anonymization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from .sanitizer import load_rules, sanitize_tree, write_reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="course-anonymizer",
        description="Create an anonymized copy of course files without changing the source tree.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sanitize = subparsers.add_parser(
        "sanitize",
        help="Copy a course directory while replacing configured personal information.",
    )
    sanitize.add_argument("input", type=Path, help="Course directory to sanitize.")
    sanitize.add_argument(
        "--config",
        required=True,
        type=Path,
        help="JSON privacy map with source/replacement rules.",
    )
    sanitize.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination directory for the sanitized copy. Must be empty or absent.",
    )
    sanitize.add_argument(
        "--report",
        required=True,
        type=Path,
        help="JSON report path. A Markdown summary is written next to it by default.",
    )
    sanitize.add_argument(
        "--markdown-report",
        type=Path,
        help="Optional Markdown summary path. Defaults to REPORT with a .md suffix.",
    )
    return parser


def run(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    if args.command != "sanitize":
        raise ValueError(f"unknown command: {args.command}")

    rules = load_rules(args.config)
    markdown_report = args.markdown_report or args.report.with_suffix(".md")
    report = sanitize_tree(args.input, args.output, rules)
    write_reports(report, args.report, markdown_report)

    stdout.write(
        f"Sanitized {report.summary['files_written']} file(s) to {args.output}\n"
        f"JSON report: {args.report}\n"
        f"Markdown report: {markdown_report}\n"
    )
    if report.summary["warnings"] or report.summary["unverified_binary_files"]:
        stderr.write(
            "Warning: "
            f"{report.summary['unverified_binary_files']} unverified binary file(s) retained; "
            f"{report.summary['warnings']} additional warning(s). See the report for details.\n"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, sys.stdout, sys.stderr)
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior.
        parser.exit(1, f"course-anonymizer: error: {exc}\n")
