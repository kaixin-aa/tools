"""Summarize text from files or standard input."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, TextIO


WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")


@dataclass(frozen=True)
class TextStats:
    characters: int
    characters_no_whitespace: int
    words: int
    lines: int
    sentences: int
    paragraphs: int


def analyze_text(text: str) -> TextStats:
    """Return basic counts for a block of text."""
    stripped = text.strip()
    paragraphs = 0
    if stripped:
        paragraphs = len([part for part in re.split(r"\n\s*\n", stripped) if part.strip()])

    return TextStats(
        characters=len(text),
        characters_no_whitespace=sum(1 for char in text if not char.isspace()),
        words=len(WORD_RE.findall(text)),
        lines=0 if text == "" else text.count("\n") + (0 if text.endswith("\n") else 1),
        sentences=len(SENTENCE_RE.findall(text)),
        paragraphs=paragraphs,
    )


def combine_stats(stats: Iterable[TextStats]) -> TextStats:
    """Add multiple TextStats values together."""
    totals = {
        "characters": 0,
        "characters_no_whitespace": 0,
        "words": 0,
        "lines": 0,
        "sentences": 0,
        "paragraphs": 0,
    }
    for item in stats:
        for key, value in asdict(item).items():
            totals[key] += value
    return TextStats(**totals)


def read_inputs(paths: list[Path], stdin: TextIO) -> list[tuple[str, str]]:
    """Read named files or stdin and return display names with content."""
    if not paths:
        return [("-", stdin.read())]

    inputs = []
    for path in paths:
        inputs.append((str(path), path.read_text(encoding="utf-8")))
    return inputs


def format_table(rows: list[tuple[str, TextStats]]) -> str:
    headers = [
        "source",
        "chars",
        "chars_no_ws",
        "words",
        "lines",
        "sentences",
        "paragraphs",
    ]
    values = [
        [
            source,
            str(stats.characters),
            str(stats.characters_no_whitespace),
            str(stats.words),
            str(stats.lines),
            str(stats.sentences),
            str(stats.paragraphs),
        ]
        for source, stats in rows
    ]

    widths = [
        max(len(row[index]) for row in [headers, *values])
        for index in range(len(headers))
    ]

    def render(row: list[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    return "\n".join([render(headers), render(["-" * width for width in widths]), *map(render, values)])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize characters, words, lines, sentences, and paragraphs in text.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="UTF-8 text files to analyze. Reads stdin when omitted.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--total",
        action="store_true",
        help="Include a total row when multiple files are provided.",
    )
    return parser


def run(args: argparse.Namespace, stdin: TextIO, stdout: TextIO) -> int:
    inputs = read_inputs(args.paths, stdin)
    rows = [(source, analyze_text(text)) for source, text in inputs]

    if args.total and len(rows) > 1:
        rows.append(("TOTAL", combine_stats(stats for _, stats in rows)))

    if args.json:
        payload = [
            {"source": source, **asdict(stats)}
            for source, stats in rows
        ]
        json.dump(payload, stdout, indent=2)
        stdout.write("\n")
    else:
        stdout.write(format_table(rows))
        stdout.write("\n")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args, sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
