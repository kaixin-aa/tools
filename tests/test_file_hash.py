from __future__ import annotations

import hashlib
import io
import json

import pytest

from daily_tools.file_hash import build_parser, hash_stream, run


def test_hash_stream_matches_hashlib_sha256() -> None:
    data = io.BytesIO(b"hello world")

    digest = hash_stream(data, algorithm="sha256", chunk_size=4)

    assert digest == hashlib.sha256(b"hello world").hexdigest()


def test_run_reads_stdin_and_writes_json() -> None:
    parser = build_parser()
    args = parser.parse_args(["--json", "--algorithm", "md5"])
    stdout = io.StringIO()

    exit_code = run(args, io.BytesIO(b"abc"), stdout)

    assert exit_code == 0
    assert json.loads(stdout.getvalue()) == [
        {
            "source": "-",
            "algorithm": "md5",
            "digest": hashlib.md5(b"abc").hexdigest(),
        }
    ]


def test_run_hashes_multiple_files_in_plain_text(tmp_path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args([str(first), str(second)])
    stdout = io.StringIO()

    exit_code = run(args, io.BytesIO(), stdout)

    assert exit_code == 0
    lines = stdout.getvalue().strip().splitlines()
    assert lines == [
        f"sha256  {hashlib.sha256(b'alpha').hexdigest()}  {first}",
        f"sha256  {hashlib.sha256(b'beta').hexdigest()}  {second}",
    ]


def test_run_rejects_non_positive_chunk_size() -> None:
    parser = build_parser()
    args = parser.parse_args(["--chunk-size", "0"])

    with pytest.raises(ValueError, match="positive integer"):
        run(args, io.BytesIO(b"abc"), io.StringIO())
