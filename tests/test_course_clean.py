from __future__ import annotations

import io
import json

import pytest

from course_clean.cli import build_parser, run
from course_clean.cleaner import (
    CleanRules,
    copy_clean_tree,
    default_rules,
    scan_tree,
    write_reports,
)


def test_scan_tree_reports_generated_directories_and_files(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "notes.md").write_text("keep", encoding="utf-8")
    idea = source / ".idea"
    idea.mkdir()
    (idea / "workspace.xml").write_text("<project />", encoding="utf-8")
    target = source / "target"
    target.mkdir()
    (target / "App.class").write_bytes(b"\xca\xfe\xba\xbe")
    (source / ".DS_Store").write_bytes(b"metadata")
    (source / "App.class").write_bytes(b"\xca\xfe\xba\xbe")

    report = scan_tree(source, default_rules())

    assert report.summary["files_seen"] == 3
    assert report.summary["files_skipped"] == 2
    assert report.summary["directories_skipped"] == 2
    assert report.reason_counts == {
        "excluded_directory": 2,
        "excluded_file_name": 1,
        "excluded_suffix": 1,
    }


def test_copy_clean_tree_keeps_source_and_excludes_upload_unfriendly_items(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "notes.md").write_text("keep", encoding="utf-8")
    (source / "App.class").write_bytes(b"\xca\xfe\xba\xbe")
    out_dir = source / "out"
    out_dir.mkdir()
    (out_dir / "artifact.txt").write_text("generated", encoding="utf-8")
    output = tmp_path / "cleaned"

    report = copy_clean_tree(source, output, default_rules())

    assert (source / "App.class").exists()
    assert (source / "out" / "artifact.txt").exists()
    assert (output / "notes.md").read_text(encoding="utf-8") == "keep"
    assert not (output / "App.class").exists()
    assert not (output / "out").exists()
    assert report.summary["files_copied"] == 1
    assert report.summary["files_skipped"] == 1
    assert report.summary["directories_skipped"] == 1


def test_copy_clean_tree_rejects_nonempty_output(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    output = tmp_path / "cleaned"
    output.mkdir()
    (output / "existing.txt").write_text("exists", encoding="utf-8")

    with pytest.raises(ValueError, match="not empty"):
        copy_clean_tree(source, output, default_rules())


def test_copy_clean_tree_rejects_output_inside_input(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()

    with pytest.raises(ValueError, match="must not be inside"):
        copy_clean_tree(source, source / "cleaned", default_rules())


def test_large_file_threshold_can_be_disabled(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "large.zip").write_bytes(b"x" * 20)

    strict_rules = CleanRules(max_size_bytes=10)
    strict_report = scan_tree(source, strict_rules)
    relaxed_rules = default_rules().with_overrides(max_size_mib=0)
    relaxed_report = scan_tree(source, relaxed_rules)

    assert strict_report.reason_counts["large_file"] == 1
    assert relaxed_report.summary["files_skipped"] == 0


def test_rule_overrides_can_keep_and_exclude_names(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / ".idea").mkdir()
    (source / ".idea" / "workspace.xml").write_text("keep", encoding="utf-8")
    (source / "private.dat").write_bytes(b"skip")
    rules = default_rules().with_overrides(
        keep_names=[".idea"],
        exclude_suffixes=[".dat"],
    )

    report = scan_tree(source, rules)

    assert report.summary["directories_skipped"] == 0
    assert report.reason_counts["excluded_suffix"] == 1


def test_write_reports_writes_json_and_markdown(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "App.class").write_bytes(b"\xca\xfe\xba\xbe")
    report = scan_tree(source, default_rules())
    json_report = tmp_path / "cleanup_report.json"
    markdown_report = tmp_path / "cleanup_report.md"

    write_reports(report, json_report, markdown_report)

    data = json.loads(json_report.read_text(encoding="utf-8"))
    assert data["summary"]["files_skipped"] == 1
    assert "Course Clean Report" in markdown_report.read_text(encoding="utf-8")


def test_cli_scan_writes_report(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "App.class").write_bytes(b"\xca\xfe\xba\xbe")
    report = tmp_path / "cleanup_report.json"
    parser = build_parser()
    args = parser.parse_args(["scan", str(source), "--report", str(report)])
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(args, stdout, stderr)

    assert exit_code == 0
    assert "scan complete" in stdout.getvalue()
    assert "Skipped items" in stderr.getvalue()
    assert report.exists()
    assert report.with_suffix(".md").exists()


def test_cli_copy_writes_cleaned_output(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "notes.md").write_text("keep", encoding="utf-8")
    (source / "App.class").write_bytes(b"\xca\xfe\xba\xbe")
    output = tmp_path / "cleaned"
    report = tmp_path / "cleanup_report.json"
    parser = build_parser()
    args = parser.parse_args(
        ["copy", str(source), "--output", str(output), "--report", str(report)]
    )

    exit_code = run(args, io.StringIO(), io.StringIO())

    assert exit_code == 0
    assert (output / "notes.md").exists()
    assert not (output / "App.class").exists()
