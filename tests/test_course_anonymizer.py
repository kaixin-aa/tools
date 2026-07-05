from __future__ import annotations

import io
import json
import zipfile

from course_anonymizer.cli import build_parser, run
from course_anonymizer.sanitizer import (
    ReplacementRule,
    load_rules,
    sanitize_tree,
    write_reports,
)


def rules() -> list[ReplacementRule]:
    return [
        ReplacementRule(source="班操", replacement="匿名同学", label="student_name"),
        ReplacementRule(source="2210101039", replacement="0000000000", label="student_id"),
        ReplacementRule(source="kaixin ban", replacement="anonymous author", label="office_author"),
    ]


def test_load_rules_accepts_privacy_map(tmp_path) -> None:
    config = tmp_path / "privacy-map.json"
    config.write_text(
        json.dumps(
            {
                "replacements": [
                    {
                        "label": "student_name",
                        "source": "班操",
                        "replacement": "匿名同学",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_rules(config)

    assert loaded == [
        ReplacementRule(source="班操", replacement="匿名同学", label="student_name")
    ]


def test_sanitize_tree_renames_paths_and_replaces_text(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "2210101039_班操_作业.txt").write_text(
        "姓名：班操\n学号：2210101039\n", encoding="utf-8"
    )
    output = tmp_path / "output"

    report = sanitize_tree(source, output, rules())

    sanitized = output / "0000000000_匿名同学_作业.txt"
    assert sanitized.read_text(encoding="utf-8") == "姓名：匿名同学\n学号：0000000000\n"
    assert report.summary["paths_changed"] == 1
    assert report.summary["content_changes"] == 1
    assert report.summary["replacement_count"] == 2


def test_sanitize_tree_handles_path_collisions(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "班操.txt").write_text("a", encoding="utf-8")
    (source / "匿名同学.txt").write_text("b", encoding="utf-8")
    output = tmp_path / "output"

    sanitize_tree(source, output, rules())

    assert (output / "匿名同学.txt").exists()
    assert (output / "匿名同学__duplicate_1.txt").exists()


def test_sanitize_tree_rewrites_ooxml_body_and_metadata(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    docx = source / "班操.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml", "<w:t>班操 2210101039</w:t>")
        archive.writestr("docProps/core.xml", "<dc:creator>kaixin ban</dc:creator>")
        archive.writestr("[Content_Types].xml", "<Types></Types>")

    output = tmp_path / "output"
    report = sanitize_tree(source, output, rules())

    sanitized_docx = output / "匿名同学.docx"
    with zipfile.ZipFile(sanitized_docx) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        core_xml = archive.read("docProps/core.xml").decode("utf-8")
    assert "班操" not in document_xml
    assert "2210101039" not in document_xml
    assert "kaixin ban" not in core_xml
    assert "匿名同学" in document_xml
    assert "anonymous author" in core_xml
    assert report.summary["content_changes"] == 2


def test_sanitize_tree_rewrites_archive_paths_and_text_members(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    archive_path = source / "作业.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("2210101039_班操/readme.txt", "班操 2210101039")
        archive.writestr("2210101039_班操/binary.class", b"\xca\xfe\xba\xbe")

    output = tmp_path / "output"
    report = sanitize_tree(source, output, rules())

    with zipfile.ZipFile(output / "作业.zip") as archive:
        names = archive.namelist()
        content = archive.read("0000000000_匿名同学/readme.txt").decode("utf-8")
    assert "0000000000_匿名同学/readme.txt" in names
    assert content == "匿名同学 0000000000"
    assert report.summary["unverified_binary_files"] == 1
    assert report.unverified_binary_counts[".class"] == 1


def test_sanitize_tree_reports_unsupported_binary_without_failing(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "班操.pdf").write_bytes(b"%PDF-1.4 fake pdf")
    output = tmp_path / "output"

    report = sanitize_tree(source, output, rules())

    assert (output / "匿名同学.pdf").read_bytes() == b"%PDF-1.4 fake pdf"
    assert report.summary["warnings"] == 0
    assert report.summary["unverified_binary_files"] == 1
    assert report.unverified_binary_counts[".pdf"] == 1


def test_write_reports_does_not_include_source_values(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "班操.txt").write_text("班操", encoding="utf-8")
    output = tmp_path / "output"
    report = sanitize_tree(source, output, rules())
    json_report = tmp_path / "privacy_report.json"
    markdown_report = tmp_path / "privacy_report.md"

    write_reports(report, json_report, markdown_report)

    assert "班操" not in json_report.read_text(encoding="utf-8")
    assert "2210101039" not in json_report.read_text(encoding="utf-8")
    assert "班操" not in markdown_report.read_text(encoding="utf-8")


def test_cli_sanitize_writes_reports(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "班操.txt").write_text("班操", encoding="utf-8")
    config = tmp_path / "privacy-map.json"
    config.write_text(
        json.dumps(
            {
                "replacements": [
                    {
                        "label": "student_name",
                        "source": "班操",
                        "replacement": "匿名同学",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    json_report = tmp_path / "privacy_report.json"
    parser = build_parser()
    args = parser.parse_args(
        [
            "sanitize",
            str(source),
            "--config",
            str(config),
            "--output",
            str(output),
            "--report",
            str(json_report),
        ]
    )

    exit_code = run(args, io.StringIO(), io.StringIO())

    assert exit_code == 0
    assert (output / "匿名同学.txt").exists()
    assert json_report.exists()
    assert json_report.with_suffix(".md").exists()
