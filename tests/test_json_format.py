from __future__ import annotations

import io
import json

import pytest

from daily_tools.json_format import build_parser, format_json, run


def test_run_pretty_prints_stdin_json() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO('{"b":1,"a":2}'), stdout)

    assert exit_code == 0
    assert stdout.getvalue() == '{\n  "b": 1,\n  "a": 2\n}\n'


def test_run_minifies_and_sorts_keys_from_file(tmp_path) -> None:
    source = tmp_path / "payload.json"
    source.write_text('{"b": 1, "a": 2}', encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["--file", str(source), "--minify", "--sort-keys"])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO(), stdout)

    assert exit_code == 0
    assert stdout.getvalue() == '{"a":2,"b":1}'


def test_format_json_rejects_negative_indent() -> None:
    with pytest.raises(ValueError, match="zero or greater"):
        format_json({"ok": True}, indent=-1, minify=False, sort_keys=False)


def test_run_preserves_unicode_characters() -> None:
    parser = build_parser()
    args = parser.parse_args(["--minify"])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO(json.dumps({"name": "上海"}, ensure_ascii=False)), stdout)

    assert exit_code == 0
    assert stdout.getvalue() == '{"name":"上海"}'
