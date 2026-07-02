"""Extract selected columns from CSV input."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import TextIO


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract selected columns from a CSV file or standard input.",
    )
    parser.add_argument(
        "columns",
        nargs="+",
        help="Column names to keep, in output order.",
    )
    parser.add_argument(
        "--file",
        dest="path",
        type=Path,
        help="CSV file to read. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="Single-character CSV delimiter. Defaults to ','.",
    )
    return parser


def validate_delimiter(delimiter: str) -> None:
    if len(delimiter) != 1:
        raise ValueError("delimiter must be a single character")


def run(args: argparse.Namespace, stdin: TextIO, stdout: TextIO) -> int:
    validate_delimiter(args.delimiter)

    if args.path is None:
        source: TextIO = stdin
        close_source = False
    else:
        source = args.path.open("r", encoding="utf-8", newline="")
        close_source = True

    try:
        reader = csv.DictReader(source, delimiter=args.delimiter)
        if reader.fieldnames is None:
            raise ValueError("input is missing a header row")

        missing = [column for column in args.columns if column not in reader.fieldnames]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"unknown column(s): {missing_text}")

        writer = csv.DictWriter(
            stdout,
            fieldnames=args.columns,
            delimiter=args.delimiter,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in reader:
            writer.writerow({column: row[column] for column in args.columns})
    finally:
        if close_source:
            source.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args, sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
