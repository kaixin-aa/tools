from __future__ import annotations

import io
import json

from daily_tools.text_stats import analyze_text, build_parser, run


def test_analyze_text_counts_core_metrics() -> None:
    text = "Hello world!\nThis is a test.\n\nSecond paragraph?"

    stats = analyze_text(text)

    assert stats.characters == 47
    assert stats.characters_no_whitespace == 39
    assert stats.words == 8
    assert stats.lines == 4
    assert stats.sentences == 3
    assert stats.paragraphs == 2


def test_run_reads_stdin_and_writes_json() -> None:
    parser = build_parser()
    args = parser.parse_args(["--json"])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO("One sentence."), stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload == [
        {
            "source": "-",
            "characters": 13,
            "characters_no_whitespace": 12,
            "words": 2,
            "lines": 1,
            "sentences": 1,
            "paragraphs": 1,
        }
    ]


def test_run_can_include_totals_for_multiple_files(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha beta", encoding="utf-8")
    second.write_text("gamma", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["--json", "--total", str(first), str(second)])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO(), stdout)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert [row["source"] for row in payload] == [str(first), str(second), "TOTAL"]
    assert payload[-1]["words"] == 3
