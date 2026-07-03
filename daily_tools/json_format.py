"""Format JSON from a file or standard input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pretty-print or minify JSON from a file or standard input.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="JSON file to read. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indent width for pretty output. Defaults to 2.",
    )
    parser.add_argument(
        "--minify",
        action="store_true",
        help="Write compact JSON without extra whitespace.",
    )
    parser.add_argument(
        "--sort-keys",
        action="store_true",
        help="Sort object keys in the output.",
    )
    return parser


def read_input(path: Path | None, stdin: TextIO) -> str:
    if path is None:
        return stdin.read()
    return path.read_text(encoding="utf-8")


def format_json(value: Any, *, indent: int, minify: bool, sort_keys: bool) -> str:
    if indent < 0:
        raise ValueError("indent must be zero or greater")

    if minify:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys)

    return json.dumps(value, ensure_ascii=False, indent=indent, sort_keys=sort_keys) + "\n"


def run(args: argparse.Namespace, stdin: TextIO, stdout: TextIO) -> int:
    raw = read_input(args.file, stdin)
    value = json.loads(raw)
    stdout.write(
        format_json(
            value,
            indent=args.indent,
            minify=args.minify,
            sort_keys=args.sort_keys,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args, sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
