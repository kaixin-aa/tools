"""Command line interface for course-clean."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from .cleaner import (
    DEFAULT_MAX_SIZE_MIB,
    CleanRules,
    copy_clean_tree,
    default_rules,
    scan_tree,
    write_reports,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="course-clean",
        description="Scan or copy a course directory while excluding generated files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Report files that would be skipped.")
    add_common_arguments(scan)

    copy = subparsers.add_parser("copy", help="Create a cleaned copy of a course directory.")
    add_common_arguments(copy)
    copy.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination directory for the cleaned copy. Must be empty or absent.",
    )
    return parser


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, help="Course directory to scan or copy.")
    parser.add_argument(
        "--report",
        required=True,
        type=Path,
        help="JSON report path. A Markdown summary is written next to it by default.",
    )
    parser.add_argument(
        "--markdown-report",
        type=Path,
        help="Optional Markdown summary path. Defaults to REPORT with a .md suffix.",
    )
    parser.add_argument(
        "--max-size-mib",
        type=int,
        default=DEFAULT_MAX_SIZE_MIB,
        help=f"Skip files larger than this size in MiB. Use 0 to disable. Defaults to {DEFAULT_MAX_SIZE_MIB}.",
    )
    parser.add_argument(
        "--exclude-name",
        action="append",
        default=[],
        help="Additional file or directory name to skip. Can be used multiple times.",
    )
    parser.add_argument(
        "--exclude-suffix",
        action="append",
        default=[],
        help="Additional file suffix to skip, such as .zip. Can be used multiple times.",
    )
    parser.add_argument(
        "--keep-name",
        action="append",
        default=[],
        help="Built-in file or directory name to keep. Can be used multiple times.",
    )


def rules_from_args(args: argparse.Namespace) -> CleanRules:
    return default_rules().with_overrides(
        exclude_names=args.exclude_name,
        exclude_suffixes=args.exclude_suffix,
        keep_names=args.keep_name,
        max_size_mib=args.max_size_mib,
    )


def run(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    rules = rules_from_args(args)
    markdown_report = args.markdown_report or args.report.with_suffix(".md")

    if args.command == "scan":
        report = scan_tree(args.input, rules)
    elif args.command == "copy":
        report = copy_clean_tree(args.input, args.output, rules)
    else:
        raise ValueError(f"unknown command: {args.command}")

    write_reports(report, args.report, markdown_report)
    stdout.write(
        f"{args.command} complete: "
        f"{format_count(report.summary['files_skipped'], 'file')} skipped, "
        f"{format_count(report.summary['directories_skipped'], 'directory')} skipped.\n"
        f"JSON report: {args.report}\n"
        f"Markdown report: {markdown_report}\n"
    )
    if report.summary["files_skipped"] or report.summary["directories_skipped"]:
        stderr.write("Skipped items were found. Review the report before publishing.\n")
    return 0


def format_count(count: int, singular: str) -> str:
    if count == 1:
        return f"{count} {singular}"
    if singular.endswith("y"):
        return f"{count} {singular[:-1]}ies"
    return f"{count} {singular}s"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, sys.stdout, sys.stderr)
    except Exception as exc:  # pragma: no cover - exercised by command-line use.
        parser.exit(1, f"course-clean: error: {exc}\n")
