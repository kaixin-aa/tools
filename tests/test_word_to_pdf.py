from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Sequence

import pytest

from word_to_pdf import backends
from word_to_pdf.backends import BackendJob, BackendResult
from word_to_pdf.cli import build_parser, run
from word_to_pdf.converter import (
    build_jobs,
    convert_directory,
    discover_word_files,
    validate_report_paths,
    write_reports,
)


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


class FakeBackend:
    name = "fake"

    def __init__(
        self,
        *,
        failures: set[str] | None = None,
        invalid: set[str] | None = None,
    ) -> None:
        self.failures = failures or set()
        self.invalid = invalid or set()
        self.jobs: list[BackendJob] = []

    def convert_batch(self, jobs: Sequence[BackendJob]) -> list[BackendResult]:
        self.jobs = list(jobs)
        results: list[BackendResult] = []
        for job in jobs:
            if job.key in self.failures:
                job.destination.write_bytes(b"partial")
                results.append(BackendResult(job.key, False, "simulated failure"))
                continue
            if job.key in self.invalid:
                job.destination.write_bytes(b"not a pdf")
            else:
                job.destination.write_bytes(PDF_BYTES)
            results.append(BackendResult(job.key, True, page_count=2))
        return results


def test_discover_word_files_supports_formats_and_skips_lock_files(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    for index, suffix in enumerate((".doc", ".DOCX", ".docm", ".dot", ".dotx", ".dotm", ".rtf")):
        (source / f"file-{index}{suffix}").write_bytes(b"word")
    (source / "~$draft.docx").write_bytes(b"lock")
    (source / "notes.txt").write_text("ignore", encoding="utf-8")

    documents, temporary = discover_word_files(source)

    assert len(documents) == 7
    assert [path.name for path in temporary] == ["~$draft.docx"]


def test_convert_directory_outputs_only_pdfs_and_preserves_structure(tmp_path) -> None:
    source = tmp_path / "course"
    nested = source / "exams"
    nested.mkdir(parents=True)
    (source / "notes.txt").write_text("do not copy", encoding="utf-8")
    (source / "lesson.doc").write_bytes(b"doc")
    (nested / "answer.docx").write_bytes(b"docx")
    output = tmp_path / "pdfs"

    report = convert_directory(source, output, FakeBackend())

    assert (output / "lesson.pdf").read_bytes() == PDF_BYTES
    assert (output / "exams" / "answer.pdf").read_bytes() == PDF_BYTES
    assert not (output / "notes.txt").exists()
    assert not list(output.rglob("*.doc*"))
    assert (source / "lesson.doc").read_bytes() == b"doc"
    assert report.summary == {
        "word_files_found": 2,
        "converted": 2,
        "failed": 0,
        "skipped": 0,
        "pdf_bytes": len(PDF_BYTES) * 2,
        "pages_reported": 4,
    }


def test_partial_failure_continues_and_removes_partial_pdf(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "good.docx").write_bytes(b"good")
    (source / "bad.doc").write_bytes(b"bad")
    output = tmp_path / "pdfs"

    report = convert_directory(
        source,
        output,
        FakeBackend(failures={"bad.doc"}),
    )

    assert (output / "good.pdf").exists()
    assert not (output / "bad.pdf").exists()
    assert report.summary["converted"] == 1
    assert report.summary["failed"] == 1


def test_invalid_backend_output_is_reported_and_removed(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "broken.docx").write_bytes(b"source")
    output = tmp_path / "pdfs"

    report = convert_directory(
        source,
        output,
        FakeBackend(invalid={"broken.docx"}),
    )

    assert report.summary["failed"] == 1
    assert "PDF header" in (report.items[0].reason or "")
    assert not (output / "broken.pdf").exists()


def test_build_jobs_rejects_pdf_name_collisions(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    first = source / "same.doc"
    second = source / "same.docx"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    with pytest.raises(ValueError, match="same PDF"):
        build_jobs(source, tmp_path / "pdfs", [first, second])


def test_convert_rejects_nonempty_output(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "file.docx").write_bytes(b"source")
    output = tmp_path / "pdfs"
    output.mkdir()
    (output / "existing.pdf").write_bytes(PDF_BYTES)

    with pytest.raises(ValueError, match="not empty"):
        convert_directory(source, output, FakeBackend())


def test_convert_rejects_output_inside_input(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()

    with pytest.raises(ValueError, match="must not be inside"):
        convert_directory(source, source / "pdfs", FakeBackend())


def test_report_paths_cannot_modify_source_or_overlap(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    output = tmp_path / "pdfs"
    report = tmp_path / "report.json"

    with pytest.raises(ValueError, match="must be different"):
        validate_report_paths(source, output, report, report)
    with pytest.raises(ValueError, match="must not be inside"):
        validate_report_paths(
            source,
            output,
            source / "report.json",
            tmp_path / "report.md",
        )
    with pytest.raises(ValueError, match="PDF output"):
        validate_report_paths(
            source,
            output,
            output / "report.json",
            tmp_path / "report.md",
        )


def test_write_reports_creates_json_and_bilingual_markdown(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "lesson.docx").write_bytes(b"source")
    report = convert_directory(source, tmp_path / "pdfs", FakeBackend())
    json_path = tmp_path / "reports" / "conversion.json"
    markdown_path = tmp_path / "reports" / "conversion.md"

    write_reports(report, json_path, markdown_path)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["summary"]["converted"] == 1
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Word to PDF Report" in markdown
    assert "转换成功" in markdown


def test_cli_success_writes_reports(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "lesson.docx").write_bytes(b"source")
    output = tmp_path / "pdfs"
    report = tmp_path / "conversion.json"
    args = build_parser().parse_args(
        ["convert", str(source), "--output", str(output), "--report", str(report)]
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run(args, stdout, stderr, backend=FakeBackend())

    assert exit_code == 0
    assert "1 converted" in stdout.getvalue()
    assert stderr.getvalue() == ""
    assert report.exists()
    assert report.with_suffix(".md").exists()


def test_cli_returns_one_when_any_document_fails(tmp_path) -> None:
    source = tmp_path / "course"
    source.mkdir()
    (source / "bad.doc").write_bytes(b"source")
    args = build_parser().parse_args(
        [
            "convert",
            str(source),
            "--output",
            str(tmp_path / "pdfs"),
            "--report",
            str(tmp_path / "conversion.json"),
        ]
    )
    stderr = io.StringIO()

    exit_code = run(
        args,
        io.StringIO(),
        stderr,
        backend=FakeBackend(failures={"bad.doc"}),
    )

    assert exit_code == 1
    assert "failed" in stderr.getvalue()


def test_choose_backend_auto_prefers_word(monkeypatch) -> None:
    monkeypatch.setattr(backends.WordBackend, "available", classmethod(lambda cls: True))
    monkeypatch.setattr(backends, "find_powershell", lambda: Path("powershell.exe"))
    monkeypatch.setattr(
        backends.LibreOfficeBackend,
        "available",
        classmethod(lambda cls: True),
    )

    selected = backends.choose_backend("auto")

    assert isinstance(selected, backends.WordBackend)
