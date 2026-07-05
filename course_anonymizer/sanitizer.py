"""Core anonymization logic for course file trees."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


TEXT_EXTENSIONS = {
    "",
    ".bat",
    ".c",
    ".cfg",
    ".cmd",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".go",
    ".h",
    ".hpp",
    ".htm",
    ".html",
    ".iml",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsp",
    ".jsx",
    ".log",
    ".m",
    ".md",
    ".mf",
    ".php",
    ".properties",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".svg",
    ".tex",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}

TEXT_FILENAMES = {
    ".gitignore",
    ".gitattributes",
    "makefile",
    "readme",
}

OOXML_EXTENSIONS = {
    ".docm",
    ".docx",
    ".dotm",
    ".dotx",
    ".potm",
    ".potx",
    ".ppsm",
    ".ppsx",
    ".pptm",
    ".pptx",
    ".xlsm",
    ".xlsx",
    ".xltm",
    ".xltx",
}

ARCHIVE_EXTENSIONS = {
    ".jar",
    ".war",
    ".zip",
}

UNVERIFIED_BINARY_EXTENSIONS = {
    ".7z",
    ".bmp",
    ".class",
    ".db",
    ".dll",
    ".doc",
    ".exe",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mdb",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".rar",
    ".so",
    ".sqlite",
    ".tif",
    ".tiff",
    ".webp",
    ".xls",
}

SKIP_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".pytest_cache",
    ".svn",
    "__pycache__",
}


@dataclass(frozen=True)
class ReplacementRule:
    """A single configured replacement rule."""

    source: str
    replacement: str
    label: str


@dataclass
class Finding:
    """One reportable action or warning."""

    severity: str
    kind: str
    path: str
    detail: str
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class SanitizeReport:
    """Privacy-safe report for a sanitize run."""

    source_root: str
    output_root: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    findings: list[Finding] = field(default_factory=list)
    unverified_binary_counts: dict[str, int] = field(default_factory=dict)
    unverified_binary_samples: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, int] = field(
        default_factory=lambda: {
            "files_seen": 0,
            "files_written": 0,
            "archive_entries_seen": 0,
            "paths_changed": 0,
            "content_changes": 0,
            "replacement_count": 0,
            "unverified_binary_files": 0,
            "warnings": 0,
            "errors": 0,
        }
    )

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)
        if finding.severity == "warning":
            self.summary["warnings"] += 1
        elif finding.severity == "error":
            self.summary["errors"] += 1

        if finding.kind in {"path_renamed", "archive_path_renamed"}:
            self.summary["paths_changed"] += 1
        if finding.kind in {"content_replaced", "archive_content_replaced"}:
            self.summary["content_changes"] += 1
            self.summary["replacement_count"] += sum(finding.counts.values())

    def add_unverified_binary(self, path: str, detail: str, extension: str) -> None:
        key = extension or "[no extension]"
        self.summary["unverified_binary_files"] += 1
        self.unverified_binary_counts[key] = self.unverified_binary_counts.get(key, 0) + 1
        if len(self.unverified_binary_samples) < 100:
            self.unverified_binary_samples.append(
                {
                    "path": path,
                    "extension": key,
                    "detail": detail,
                }
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_root": self.source_root,
            "output_root": self.output_root,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "unverified_binary_counts": self.unverified_binary_counts,
            "unverified_binary_samples": self.unverified_binary_samples,
            "findings": [
                {
                    "severity": finding.severity,
                    "kind": finding.kind,
                    "path": finding.path,
                    "detail": finding.detail,
                    "counts": finding.counts,
                }
                for finding in self.findings
            ],
        }


def load_rules(config_path: Path) -> list[ReplacementRule]:
    """Load replacement rules from a JSON privacy map."""

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "replacements" in raw:
        raw_rules = raw["replacements"]
    else:
        raw_rules = raw

    if isinstance(raw_rules, dict):
        items = [
            {"source": source, "replacement": replacement}
            for source, replacement in raw_rules.items()
        ]
    elif isinstance(raw_rules, list):
        items = raw_rules
    else:
        raise ValueError("privacy map must be a JSON object or a replacements list")

    rules: list[ReplacementRule] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"replacement rule {index} must be an object")
        source = item.get("source")
        replacement = item.get("replacement")
        label = item.get("label") or f"rule_{index}"
        if not isinstance(source, str) or not source:
            raise ValueError(f"replacement rule {index} has an empty source")
        if not isinstance(replacement, str):
            raise ValueError(f"replacement rule {index} has a non-string replacement")
        if not isinstance(label, str) or not label:
            raise ValueError(f"replacement rule {index} has an invalid label")
        rules.append(ReplacementRule(source=source, replacement=replacement, label=label))

    if not rules:
        raise ValueError("privacy map must contain at least one replacement rule")

    return sorted(rules, key=lambda rule: len(rule.source), reverse=True)


def sanitize_tree(input_dir: Path, output_dir: Path, rules: Iterable[ReplacementRule]) -> SanitizeReport:
    """Create a sanitized copy of input_dir in output_dir."""

    rule_list = list(rules)
    sanitizer = Sanitizer(rule_list)
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    if not input_dir.is_dir():
        raise ValueError(f"input is not a directory: {input_dir}")
    if output_dir == input_dir or output_dir.is_relative_to(input_dir):
        raise ValueError("output directory must not be inside the input directory")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ValueError(f"output exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise ValueError(f"output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_root, _ = sanitizer.replace_text(input_dir.name)
    output_root, _ = sanitizer.replace_text(output_dir.name)
    report = SanitizeReport(source_root=source_root, output_root=output_root)
    used_targets: set[str] = set()

    for root, dirs, files in os.walk(input_dir):
        dirs[:] = [dirname for dirname in dirs if dirname not in SKIP_DIRECTORY_NAMES]
        source_root_path = Path(root)
        relative_dir = source_root_path.relative_to(input_dir)
        target_dir, dir_changed = sanitizer.sanitized_relative_path(relative_dir)
        target_root = output_dir / target_dir
        target_root.mkdir(parents=True, exist_ok=True)
        if relative_dir != Path(".") and dir_changed:
            report.add(
                Finding(
                    severity="info",
                    kind="path_renamed",
                    path=target_dir.as_posix(),
                    detail="Directory path changed by configured replacement rules.",
                )
            )

        for dirname in dirs:
            child_rel = relative_dir / dirname
            sanitized_child, _ = sanitizer.sanitized_relative_path(child_rel)
            (output_dir / sanitized_child).mkdir(parents=True, exist_ok=True)

        for filename in files:
            source_file = source_root_path / filename
            relative_file = source_file.relative_to(input_dir)
            target_relative, file_path_changed = sanitizer.sanitized_relative_path(relative_file)
            target = unique_filesystem_path(output_dir / target_relative, used_targets)
            target.parent.mkdir(parents=True, exist_ok=True)
            report.summary["files_seen"] += 1
            if file_path_changed or target.relative_to(output_dir) != target_relative:
                report.add(
                    Finding(
                        severity="info",
                        kind="path_renamed",
                        path=target.relative_to(output_dir).as_posix(),
                        detail="File path changed by configured replacement rules.",
                    )
                )
            sanitizer.process_file(source_file, target, target.relative_to(output_dir).as_posix(), report)
            report.summary["files_written"] += 1

    return report


def write_reports(report: SanitizeReport, json_path: Path, markdown_path: Path) -> None:
    """Write JSON and Markdown reports."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")


def render_markdown_report(report: SanitizeReport) -> str:
    """Render a compact Markdown summary."""

    lines = [
        "# Privacy Report",
        "",
        f"- Source root: `{report.source_root}`",
        f"- Output root: `{report.output_root}`",
        f"- Generated at: `{report.generated_at}`",
        f"- Files written: `{report.summary['files_written']}`",
        f"- Archive entries scanned: `{report.summary['archive_entries_seen']}`",
        f"- Path changes: `{report.summary['paths_changed']}`",
        f"- Content changes: `{report.summary['content_changes']}`",
        f"- Replacement count: `{report.summary['replacement_count']}`",
        f"- Unverified binary files retained: `{report.summary['unverified_binary_files']}`",
        f"- Warnings: `{report.summary['warnings']}`",
        "",
    ]
    if report.unverified_binary_counts:
        lines.extend(["## Unverified Binary Files", ""])
        for extension, count in sorted(report.unverified_binary_counts.items()):
            lines.append(f"- `{extension}`: `{count}` file(s)")
        if report.unverified_binary_samples:
            lines.extend(["", "### Sample Paths", ""])
            for sample in report.unverified_binary_samples:
                lines.append(
                    f"- `{sample['extension']}` `{sample['path']}`: {sample['detail']}"
                )
        lines.append("")

    if report.findings:
        lines.extend(["## Findings", ""])
        for finding in report.findings:
            counts = ""
            if finding.counts:
                rendered_counts = ", ".join(f"{label}: {count}" for label, count in sorted(finding.counts.items()))
                counts = f" ({rendered_counts})"
            lines.append(
                f"- `{finding.severity}` `{finding.kind}` `{finding.path}`: {finding.detail}{counts}"
            )
    else:
        lines.append("No findings.")
    lines.append("")
    return "\n".join(lines)


class Sanitizer:
    """Apply configured replacements to files, paths, archives, and OOXML packages."""

    def __init__(self, rules: list[ReplacementRule]) -> None:
        self.rules = rules

    def replace_text(self, value: str) -> tuple[str, dict[str, int]]:
        counts: dict[str, int] = {}
        result = value
        for rule in self.rules:
            count = result.count(rule.source)
            if count:
                result = result.replace(rule.source, rule.replacement)
                counts[rule.label] = counts.get(rule.label, 0) + count
        return result, counts

    def sanitized_relative_path(self, relative_path: Path) -> tuple[Path, bool]:
        if relative_path == Path("."):
            return Path("."), False

        changed = False
        parts: list[str] = []
        for part in relative_path.parts:
            sanitized, counts = self.replace_text(part)
            changed = changed or bool(counts)
            parts.append(sanitized)
        return Path(*parts), changed

    def sanitized_archive_name(self, name: str) -> tuple[str, bool]:
        normalized = name.replace("\\", "/")
        is_dir = normalized.endswith("/")
        parts = [part for part in normalized.split("/") if part not in {"", "."}]
        changed = False
        sanitized_parts: list[str] = []
        for part in parts:
            sanitized, counts = self.replace_text(part)
            changed = changed or bool(counts)
            sanitized_parts.append(sanitized)
        sanitized_name = "/".join(sanitized_parts)
        if is_dir and sanitized_name:
            sanitized_name += "/"
        return sanitized_name, changed

    def process_file(self, source: Path, target: Path, report_path: str, report: SanitizeReport) -> None:
        suffix = source.suffix.lower()
        if suffix in OOXML_EXTENSIONS:
            self._process_ooxml_file(source, target, report_path, report)
        elif suffix in ARCHIVE_EXTENSIONS:
            self._process_archive_file(source, target, report_path, report)
        else:
            data = source.read_bytes()
            processed = self._process_regular_bytes(data, source.name, report_path, report, archive_member=False)
            target.write_bytes(processed)
            copy_stat(source, target)

    def _process_ooxml_file(
        self,
        source: Path,
        target: Path,
        report_path: str,
        report: SanitizeReport,
    ) -> None:
        try:
            processed = self._process_ooxml_bytes(source.read_bytes(), report_path, report)
            target.write_bytes(processed)
            copy_stat(source, target)
        except zipfile.BadZipFile:
            shutil.copy2(source, target)
            report.add(
                Finding(
                    severity="warning",
                    kind="retained_unprocessed_ooxml",
                    path=report_path,
                    detail="OOXML file could not be opened and was copied without content changes.",
                )
            )

    def _process_archive_file(
        self,
        source: Path,
        target: Path,
        report_path: str,
        report: SanitizeReport,
    ) -> None:
        try:
            with zipfile.ZipFile(source, "r") as source_zip, zipfile.ZipFile(
                target, "w", allowZip64=True
            ) as target_zip:
                self._process_zip_entries(source_zip, target_zip, report_path, report, ooxml=False)
            copy_stat(source, target)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            shutil.copy2(source, target)
            report.add(
                Finding(
                    severity="warning",
                    kind="retained_unprocessed_archive",
                    path=report_path,
                    detail="Archive could not be processed and was copied without content changes.",
                )
            )

    def _process_ooxml_bytes(self, data: bytes, report_path: str, report: SanitizeReport) -> bytes:
        with zipfile.ZipFile(BytesIO(data), "r") as source_zip:
            output = BytesIO()
            with zipfile.ZipFile(output, "w", allowZip64=True) as target_zip:
                self._process_zip_entries(source_zip, target_zip, report_path, report, ooxml=True)
            return output.getvalue()

    def _process_archive_bytes(self, data: bytes, report_path: str, report: SanitizeReport) -> bytes:
        try:
            with zipfile.ZipFile(BytesIO(data), "r") as source_zip:
                output = BytesIO()
                with zipfile.ZipFile(output, "w", allowZip64=True) as target_zip:
                    self._process_zip_entries(source_zip, target_zip, report_path, report, ooxml=False)
                return output.getvalue()
        except (zipfile.BadZipFile, RuntimeError, OSError):
            report.add(
                Finding(
                    severity="warning",
                    kind="retained_unprocessed_archive",
                    path=report_path,
                    detail="Nested archive could not be processed and was copied without content changes.",
                )
            )
            return data

    def _process_zip_entries(
        self,
        source_zip: zipfile.ZipFile,
        target_zip: zipfile.ZipFile,
        report_path: str,
        report: SanitizeReport,
        *,
        ooxml: bool,
    ) -> None:
        used_names: set[str] = set()
        for source_info in source_zip.infolist():
            report.summary["archive_entries_seen"] += 1
            sanitized_name, name_changed = self.sanitized_archive_name(source_info.filename)
            if not sanitized_name:
                continue
            unique_name = unique_archive_name(sanitized_name, used_names, is_dir=source_info.is_dir())
            member_report_path = f"{report_path}!/{unique_name}"
            if name_changed or unique_name != sanitized_name:
                report.add(
                    Finding(
                        severity="info",
                        kind="archive_path_renamed",
                        path=member_report_path,
                        detail="Archive member path changed by configured replacement rules.",
                    )
                )

            target_info = clone_zip_info(source_info, unique_name)
            if source_info.is_dir():
                target_zip.writestr(target_info, b"")
                continue

            member_data = source_zip.read(source_info.filename)
            processed_data = self._process_member_bytes(
                member_data,
                unique_name,
                member_report_path,
                report,
                inside_ooxml=ooxml,
            )
            target_zip.writestr(target_info, processed_data)

    def _process_member_bytes(
        self,
        data: bytes,
        name: str,
        report_path: str,
        report: SanitizeReport,
        *,
        inside_ooxml: bool,
    ) -> bytes:
        suffix = PurePosixPath(name.rstrip("/")).suffix.lower()
        if suffix in OOXML_EXTENSIONS and not inside_ooxml:
            try:
                return self._process_ooxml_bytes(data, report_path, report)
            except zipfile.BadZipFile:
                report.add(
                    Finding(
                        severity="warning",
                        kind="retained_unprocessed_ooxml",
                        path=report_path,
                        detail="Nested OOXML file could not be opened and was copied without content changes.",
                    )
                )
                return data
        if suffix in ARCHIVE_EXTENSIONS and not inside_ooxml:
            return self._process_archive_bytes(data, report_path, report)

        return self._process_regular_bytes(data, name, report_path, report, archive_member=True, inside_ooxml=inside_ooxml)

    def _process_regular_bytes(
        self,
        data: bytes,
        name: str,
        report_path: str,
        report: SanitizeReport,
        *,
        archive_member: bool,
        inside_ooxml: bool = False,
    ) -> bytes:
        suffix = PurePosixPath(name).suffix.lower()
        lower_name = PurePosixPath(name).name.lower()

        if is_unverified_binary(suffix, lower_name, inside_ooxml):
            report.add_unverified_binary(
                report_path,
                "Binary file type was retained but not reliably content-sanitized.",
                suffix,
            )
            return data

        decoded = decode_text(data)
        if decoded is None:
            if suffix not in TEXT_EXTENSIONS and lower_name not in TEXT_FILENAMES:
                report.add_unverified_binary(
                    report_path,
                    "Unknown binary content was retained but not reliably content-sanitized.",
                    suffix,
                )
            return data

        text, encoding = decoded
        replaced_text, counts = self.replace_text(text)
        if not counts:
            return data

        report.add(
            Finding(
                severity="info",
                kind="archive_content_replaced" if archive_member else "content_replaced",
                path=report_path,
                detail="Text content changed by configured replacement rules.",
                counts=counts,
            )
        )
        return replaced_text.encode(encoding)


def decode_text(data: bytes) -> tuple[str, str] | None:
    """Decode bytes as text if they look like a normal text file."""

    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        encodings = ["utf-16"]
    elif data.startswith(b"\xef\xbb\xbf"):
        encodings = ["utf-8-sig", "utf-8", "gb18030"]
    else:
        encodings = ["utf-8", "gb18030"]

    for encoding in encodings:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if looks_like_text(text):
            return text, encoding
    return None


def looks_like_text(text: str) -> bool:
    if not text:
        return True
    allowed_controls = {"\n", "\r", "\t", "\f", "\b"}
    bad_controls = sum(
        1
        for char in text
        if ord(char) < 32 and char not in allowed_controls
    )
    return bad_controls / max(len(text), 1) <= 0.01


def is_unverified_binary(suffix: str, lower_name: str, inside_ooxml: bool) -> bool:
    if inside_ooxml and suffix in {".xml", ".rels", ".txt"}:
        return False
    if suffix in UNVERIFIED_BINARY_EXTENSIONS:
        return True
    if suffix in TEXT_EXTENSIONS or lower_name in TEXT_FILENAMES:
        return False
    return False


def unique_filesystem_path(path: Path, used: set[str]) -> Path:
    candidate = path
    counter = 1
    while path_key(candidate) in used or candidate.exists():
        candidate = path.with_name(f"{path.stem}__duplicate_{counter}{path.suffix}")
        counter += 1
    used.add(path_key(candidate))
    return candidate


def path_key(path: Path) -> str:
    return str(path).casefold()


def unique_archive_name(name: str, used: set[str], *, is_dir: bool) -> str:
    normalized = name.rstrip("/")
    candidate = normalized + ("/" if is_dir else "")
    counter = 1
    while candidate.casefold() in used:
        path = PurePosixPath(normalized)
        duplicate_name = f"{path.stem}__duplicate_{counter}{path.suffix}"
        if str(path.parent) in {"", "."}:
            normalized_candidate = duplicate_name
        else:
            normalized_candidate = f"{path.parent.as_posix()}/{duplicate_name}"
        candidate = normalized_candidate + ("/" if is_dir else "")
        counter += 1
    used.add(candidate.casefold())
    return candidate


def clone_zip_info(source: zipfile.ZipInfo, filename: str) -> zipfile.ZipInfo:
    target = zipfile.ZipInfo(filename=filename, date_time=source.date_time)
    target.comment = source.comment
    target.extra = source.extra
    target.internal_attr = source.internal_attr
    target.external_attr = source.external_attr
    target.create_system = source.create_system
    target.compress_type = source.compress_type
    return target


def copy_stat(source: Path, target: Path) -> None:
    try:
        shutil.copystat(source, target)
    except OSError:
        pass
