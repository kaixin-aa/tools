from __future__ import annotations

import io

import pytest

from daily_tools.csv_select import build_parser, run, validate_delimiter


def test_run_selects_requested_columns_from_stdin() -> None:
    parser = build_parser()
    args = parser.parse_args(["name", "city"])
    stdin = io.StringIO("name,age,city\nAda,36,London\nGrace,40,New York\n")
    stdout = io.StringIO()

    exit_code = run(args, stdin, stdout)

    assert exit_code == 0
    assert stdout.getvalue() == "name,city\nAda,London\nGrace,New York\n"


def test_run_reads_file_with_custom_delimiter(tmp_path) -> None:
    source = tmp_path / "people.csv"
    source.write_text("name;role;team\nAda;Engineer;Platform\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(["team", "name", "--file", str(source), "--delimiter", ";"])
    stdout = io.StringIO()

    exit_code = run(args, io.StringIO(), stdout)

    assert exit_code == 0
    assert stdout.getvalue() == "team;name\nPlatform;Ada\n"


def test_run_writes_to_output_file_with_output_delimiter(tmp_path) -> None:
    source = tmp_path / "people.csv"
    target = tmp_path / "selected" / "people.tsv"
    source.write_text("name,role,team\nAda,Engineer,Platform\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(
        [
            "team",
            "name",
            "--file",
            str(source),
            "--output",
            str(target),
            "--output-delimiter",
            "\t",
        ]
    )

    exit_code = run(args, io.StringIO(), io.StringIO())

    assert exit_code == 0
    assert target.read_text(encoding="utf-8") == "team\tname\nPlatform\tAda\n"


def test_run_selects_columns_by_index() -> None:
    parser = build_parser()
    args = parser.parse_args(["3", "1", "--by-index"])
    stdin = io.StringIO("name,age,city\nAda,36,London\n")
    stdout = io.StringIO()

    exit_code = run(args, stdin, stdout)

    assert exit_code == 0
    assert stdout.getvalue() == "city,name\nLondon,Ada\n"


def test_run_selects_no_header_rows_by_index() -> None:
    parser = build_parser()
    args = parser.parse_args(["2", "1", "--by-index", "--no-header"])
    stdin = io.StringIO("Ada,London\nGrace,New York\n")
    stdout = io.StringIO()

    exit_code = run(args, stdin, stdout)

    assert exit_code == 0
    assert stdout.getvalue() == "London,Ada\nNew York,Grace\n"


def test_run_ignore_missing_writes_empty_cells() -> None:
    parser = build_parser()
    args = parser.parse_args(["name", "country", "--ignore-missing"])
    stdin = io.StringIO("name,city\nAda,London\n")
    stdout = io.StringIO()

    exit_code = run(args, stdin, stdout)

    assert exit_code == 0
    assert stdout.getvalue() == "name,country\nAda,\n"


def test_run_rejects_unknown_columns() -> None:
    parser = build_parser()
    args = parser.parse_args(["name", "country"])

    with pytest.raises(ValueError, match="unknown column\\(s\\): country"):
        run(args, io.StringIO("name,city\nAda,London\n"), io.StringIO())


def test_validate_delimiter_requires_one_character() -> None:
    with pytest.raises(ValueError, match="single character"):
        validate_delimiter("::")


def test_run_rejects_no_header_without_by_index() -> None:
    parser = build_parser()
    args = parser.parse_args(["name", "--no-header"])

    with pytest.raises(ValueError, match="requires --by-index"):
        run(args, io.StringIO("Ada,London\n"), io.StringIO())


def test_run_rejects_out_of_range_index() -> None:
    parser = build_parser()
    args = parser.parse_args(["4", "--by-index"])

    with pytest.raises(ValueError, match="out of range"):
        run(args, io.StringIO("name,age,city\nAda,36,London\n"), io.StringIO())
