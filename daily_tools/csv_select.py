"""Extract selected columns from CSV input."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, TextIO


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
        "--output",
        type=Path,
        help="CSV file to write. Writes stdout when omitted.",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="Single-character input CSV delimiter. Defaults to ','.",
    )
    parser.add_argument(
        "--output-delimiter",
        help="Single-character output CSV delimiter. Defaults to the input delimiter.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding for --file and --output. Defaults to utf-8.",
    )
    parser.add_argument(
        "--by-index",
        action="store_true",
        help="Treat columns as 1-based column indexes instead of header names.",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Read input as data rows without a header. Requires --by-index.",
    )
    parser.add_argument(
        "--ignore-missing",
        action="store_true",
        help="Write empty cells for missing named columns instead of failing.",
    )
    return parser


def validate_delimiter(delimiter: str, *, option: str = "delimiter") -> None:
    if len(delimiter) != 1:
        raise ValueError(f"{option} must be a single character")


def parse_indexes(columns: Iterable[str]) -> list[int]:
    indexes: list[int] = []
    for column in columns:
        try:
            index = int(column)
        except ValueError as exc:
            raise ValueError(f"column index must be an integer: {column}") from exc
        if index < 1:
            raise ValueError(f"column index must be 1 or greater: {column}")
        indexes.append(index - 1)
    return indexes


def select_indexes_from_header(
    header: list[str],
    columns: list[str],
    *,
    by_index: bool,
    ignore_missing: bool,
) -> tuple[list[int | None], list[str]]:
    if by_index:
        indexes = parse_indexes(columns)
        out_of_range = [index + 1 for index in indexes if index >= len(header)]
        if out_of_range:
            rendered = ", ".join(str(index) for index in out_of_range)
            raise ValueError(
                f"column index out of range: {rendered} "
                f"(input has {len(header)} column(s))"
            )
        return indexes, [header[index] for index in indexes]

    missing = [column for column in columns if column not in header]
    if missing and not ignore_missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"unknown column(s): {missing_text}")

    indexes_by_name = {column: index for index, column in enumerate(header)}
    indexes: list[int | None] = [indexes_by_name.get(column) for column in columns]
    return indexes, columns


def selected_row(row: list[str], indexes: list[int | None]) -> list[str]:
    selected: list[str] = []
    for index in indexes:
        if index is None or index >= len(row):
            selected.append("")
        else:
            selected.append(row[index])
    return selected


def open_input(path: Path | None, stdin: TextIO, encoding: str) -> tuple[TextIO, bool]:
    if path is None:
        return stdin, False
    return path.open("r", encoding=encoding, newline=""), True


def open_output(path: Path | None, stdout: TextIO, encoding: str) -> tuple[TextIO, bool]:
    if path is None:
        return stdout, False
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding=encoding, newline=""), True


def run(args: argparse.Namespace, stdin: TextIO, stdout: TextIO) -> int:
    validate_delimiter(args.delimiter)
    output_delimiter = args.output_delimiter or args.delimiter
    validate_delimiter(output_delimiter, option="output delimiter")

    if args.no_header and not args.by_index:
        raise ValueError("--no-header requires --by-index")

    source, close_source = open_input(args.path, stdin, args.encoding)
    target, close_target = open_output(args.output, stdout, args.encoding)
    try:
        reader = csv.reader(source, delimiter=args.delimiter)
        writer = csv.writer(target, delimiter=output_delimiter, lineterminator="\n")

        if args.no_header:
            indexes = parse_indexes(args.columns)
        else:
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError("input is missing a header row") from exc
            indexes, output_header = select_indexes_from_header(
                header,
                args.columns,
                by_index=args.by_index,
                ignore_missing=args.ignore_missing,
            )
            writer.writerow(output_header)

        for row in reader:
            writer.writerow(selected_row(row, indexes))
    finally:
        if close_source:
            source.close()
        if close_target:
            target.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, sys.stdin, sys.stdout)
    except Exception as exc:  # pragma: no cover - exercised by command-line use.
        parser.exit(1, f"csv-select: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
