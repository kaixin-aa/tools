"""Recursive Word document discovery, conversion, and reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .backends import BackendJob, BackendResult, ConversionBackend


WORD_SUFFIXES = frozenset(
    {".doc", ".docx", ".docm", ".dot", ".dotx", ".dotm", ".rtf"}
)


@dataclass(frozen=True)
class ReportItem:
    """One converted, failed, or skipped source document."""

    source: str
    status: str
    output: str | None = None
    reason: str | None = None
    output_bytes: int = 0
    page_count: int | None = None


@dataclass
class ConversionReport:
    """Machine-readable result of one directory conversion."""

    source_root: str
    output_root: str
    backend: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    items: list[ReportItem] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        """Return aggregate conversion counts."""

        return {
            "word_files_found": sum(item.status != "skipped" for item in self.items),
            "converted": sum(item.status == "converted" for item in self.items),
            "failed": sum(item.status == "failed" for item in self.items),
            "skipped": sum(item.status == "skipped" for item in self.items),
            "pdf_bytes": sum(item.output_bytes for item in self.items),
            "pages_reported": sum(item.page_count or 0 for item in self.items),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable report representation."""

        return {
            "source_root": self.source_root,
            "output_root": self.output_root,
            "backend": self.backend,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "items": [
                {
                    "source": item.source,
                    "output": item.output,
                    "status": item.status,
                    "reason": item.reason,
                    "output_bytes": item.output_bytes,
                    "page_count": item.page_count,
                }
                for item in self.items
            ],
        }


def discover_word_files(input_dir: Path) -> tuple[list[Path], list[Path]]:
    """Find supported Word documents and temporary lock files recursively."""

    input_dir = validate_input_dir(input_dir)
    documents: list[Path] = []
    temporary: list[Path] = []
    for path in input_dir.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in WORD_SUFFIXES:
            continue
        if path.name.startswith("~$"):
            temporary.append(path)
        else:
            documents.append(path)
    sort_key = lambda path: path.relative_to(input_dir).as_posix().casefold()
    documents.sort(key=sort_key)
    temporary.sort(key=sort_key)
    return documents, temporary


def build_jobs(
    input_dir: Path,
    output_dir: Path,
    documents: Sequence[Path],
) -> list[BackendJob]:
    """Map source documents to PDF destinations and reject collisions."""

    jobs: list[BackendJob] = []
    destinations: dict[str, str] = {}
    for source in documents:
        relative_source = source.relative_to(input_dir)
        relative_output = relative_source.with_suffix(".pdf")
        collision_key = relative_output.as_posix().casefold()
        previous = destinations.get(collision_key)
        if previous is not None:
            raise ValueError(
                "multiple Word files map to the same PDF: "
                f"{previous} and {relative_source.as_posix()} -> "
                f"{relative_output.as_posix()}"
            )
        destinations[collision_key] = relative_source.as_posix()
        jobs.append(
            BackendJob(
                key=relative_source.as_posix(),
                source=source,
                destination=output_dir / relative_output,
            )
        )
    return jobs


def convert_directory(
    input_dir: Path,
    output_dir: Path,
    backend: ConversionBackend,
) -> ConversionReport:
    """Convert every supported Word document under an input directory."""

    input_dir = validate_input_dir(input_dir)
    output_dir = output_dir.resolve()
    validate_output_dir(input_dir, output_dir)
    documents, temporary = discover_word_files(input_dir)
    jobs = build_jobs(input_dir, output_dir, documents)

    output_dir.mkdir(parents=True, exist_ok=True)
    for job in jobs:
        job.destination.parent.mkdir(parents=True, exist_ok=True)

    report = ConversionReport(
        source_root=input_dir.name,
        output_root=output_dir.name,
        backend=backend.name,
    )
    for path in temporary:
        report.items.append(
            ReportItem(
                source=path.relative_to(input_dir).as_posix(),
                status="skipped",
                reason="temporary_word_file",
            )
        )

    try:
        backend_results = backend.convert_batch(jobs)
    except Exception as exc:
        backend_results = [
            BackendResult(job.key, False, f"backend error: {exc}") for job in jobs
        ]
    results_by_key = {result.key: result for result in backend_results}

    for job in jobs:
        relative_output = job.destination.relative_to(output_dir).as_posix()
        result = results_by_key.get(job.key)
        error = result.error if result else "backend returned no result for this file"
        if result and result.success:
            validation_error = validate_pdf(job.destination)
            if validation_error is None:
                report.items.append(
                    ReportItem(
                        source=job.key,
                        output=relative_output,
                        status="converted",
                        output_bytes=job.destination.stat().st_size,
                        page_count=result.page_count,
                    )
                )
                continue
            error = validation_error

        remove_partial_pdf(job.destination)
        report.items.append(
            ReportItem(
                source=job.key,
                output=relative_output,
                status="failed",
                reason=error or "conversion failed",
                page_count=result.page_count if result else None,
            )
        )
    return report


def validate_input_dir(input_dir: Path) -> Path:
    """Resolve and validate the source directory."""

    resolved = input_dir.resolve()
    if not resolved.is_dir():
        raise ValueError(f"input is not a directory: {input_dir}")
    return resolved


def validate_output_dir(input_dir: Path, output_dir: Path) -> None:
    """Require a separate empty destination directory."""

    if output_dir == input_dir or output_dir.is_relative_to(input_dir):
        raise ValueError("output directory must not be inside the input directory")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"output exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise ValueError(f"output directory is not empty: {output_dir}")


def validate_report_paths(
    input_dir: Path,
    output_dir: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    """Keep reports outside the source tree and PDF-only output directory."""

    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    resolved_json = json_path.resolve()
    resolved_markdown = markdown_path.resolve()
    if resolved_json == resolved_markdown:
        raise ValueError("JSON and Markdown report paths must be different")
    for report_path in (resolved_json, resolved_markdown):
        if report_path == input_dir or report_path.is_relative_to(input_dir):
            raise ValueError("report paths must not be inside the input directory")
        if report_path == output_dir or report_path.is_relative_to(output_dir):
            raise ValueError("report paths must not be inside the PDF output directory")


def validate_pdf(path: Path) -> str | None:
    """Perform a lightweight structural check on a generated PDF."""

    if not path.is_file():
        return "backend reported success but no PDF was created"
    if path.stat().st_size < 8:
        return "generated PDF is empty or truncated"
    with path.open("rb") as file:
        if file.read(5) != b"%PDF-":
            return "generated file does not have a PDF header"
    return None


def remove_partial_pdf(path: Path) -> None:
    """Remove an unusable output created during a failed conversion."""

    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def write_reports(
    report: ConversionReport,
    json_path: Path,
    markdown_path: Path,
) -> None:
    """Write JSON and Markdown conversion reports."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: ConversionReport) -> str:
    """Render a compact bilingual Markdown summary."""

    summary = report.summary
    lines = [
        "# Word to PDF Report / Word 转 PDF 报告",
        "",
        f"- Source root / 源目录: `{escape_markdown(report.source_root)}`",
        f"- Output root / 输出目录: `{escape_markdown(report.output_root)}`",
        f"- Backend / 转换后端: `{report.backend}`",
        f"- Generated at / 生成时间: `{report.generated_at}`",
        f"- Word files found / Word 文件: `{summary['word_files_found']}`",
        f"- Converted / 转换成功: `{summary['converted']}`",
        f"- Failed / 转换失败: `{summary['failed']}`",
        f"- Skipped / 已跳过: `{summary['skipped']}`",
        f"- PDF bytes / PDF 字节数: `{summary['pdf_bytes']}`",
        f"- Pages reported / 已报告页数: `{summary['pages_reported']}`",
        "",
        "## Files / 文件明细",
        "",
    ]
    if not report.items:
        lines.append("No Word documents were found. / 未发现 Word 文档。")
    for item in report.items:
        output = f" -> `{escape_markdown(item.output)}`" if item.output else ""
        details = f" ({escape_markdown(item.reason)})" if item.reason else ""
        lines.append(
            f"- `{item.status}` `{escape_markdown(item.source)}`{output}{details}"
        )
    lines.append("")
    return "\n".join(lines)


def escape_markdown(value: str | None) -> str:
    """Escape backticks used inside report code spans."""

    return (value or "").replace("`", "\\`")
