"""Document-rendering backends used by word-to-pdf."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class BackendJob:
    """One source document and its requested PDF destination."""

    key: str
    source: Path
    destination: Path


@dataclass(frozen=True)
class BackendResult:
    """The rendering result returned for one backend job."""

    key: str
    success: bool
    error: str | None = None
    page_count: int | None = None


class ConversionBackend(Protocol):
    """Interface implemented by document rendering backends."""

    name: str

    def convert_batch(self, jobs: Sequence[BackendJob]) -> list[BackendResult]:
        """Convert every job and return one result per job."""


class WordBackend:
    """Convert documents with a hidden Microsoft Word COM process."""

    name = "word"

    def __init__(
        self,
        powershell: str | Path | None = None,
        script_path: str | Path | None = None,
    ) -> None:
        detected = Path(powershell) if powershell else find_powershell()
        if detected is None:
            raise RuntimeError("Windows PowerShell was not found")
        self.powershell = detected
        self.script_path = (
            Path(script_path)
            if script_path
            else Path(__file__).with_name("word_backend.ps1")
        )

    @classmethod
    def available(cls) -> bool:
        """Return whether Windows PowerShell and Microsoft Word are registered."""

        return os.name == "nt" and find_powershell() is not None and word_is_registered()

    def convert_batch(self, jobs: Sequence[BackendJob]) -> list[BackendResult]:
        if not jobs:
            return []

        manifest = [
            {
                "key": job.key,
                "source": str(job.source),
                "destination": str(job.destination),
            }
            for job in jobs
        ]
        with tempfile.TemporaryDirectory(prefix="word-to-pdf-") as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                str(self.powershell),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.script_path),
                "-ManifestPath",
                str(manifest_path),
            ]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=max(120, len(jobs) * 60),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return failure_results(jobs, "Microsoft Word conversion timed out")
            except OSError as exc:
                return failure_results(jobs, f"could not start Microsoft Word backend: {exc}")

        payload = parse_backend_payload(completed.stdout)
        if payload is None:
            details = completed.stderr.strip() or "backend returned no valid JSON result"
            return failure_results(jobs, details)
        if payload.get("fatal_error"):
            return failure_results(jobs, str(payload["fatal_error"]))

        raw_results = payload.get("results") or []
        by_key = {str(item.get("key")): item for item in raw_results}
        results: list[BackendResult] = []
        for job in jobs:
            item = by_key.get(job.key)
            if item is None:
                results.append(
                    BackendResult(
                        key=job.key,
                        success=False,
                        error="Microsoft Word backend returned no result for this file",
                    )
                )
                continue
            page_count = item.get("page_count")
            results.append(
                BackendResult(
                    key=job.key,
                    success=bool(item.get("success")),
                    error=str(item["error"]) if item.get("error") else None,
                    page_count=int(page_count) if page_count is not None else None,
                )
            )
        return results


class LibreOfficeBackend:
    """Convert documents with the LibreOffice command line interface."""

    name = "libreoffice"

    def __init__(self, executable: str | Path | None = None) -> None:
        detected = Path(executable) if executable else find_soffice()
        if detected is None:
            raise RuntimeError("LibreOffice soffice was not found")
        self.executable = detected

    @classmethod
    def available(cls) -> bool:
        """Return whether a LibreOffice executable can be found."""

        return find_soffice() is not None

    def convert_batch(self, jobs: Sequence[BackendJob]) -> list[BackendResult]:
        results: list[BackendResult] = []
        if not jobs:
            return results

        with tempfile.TemporaryDirectory(prefix="word-to-pdf-lo-") as temp_dir:
            temp_root = Path(temp_dir)
            profile = temp_root / "profile"
            profile.mkdir()
            profile_uri = profile.resolve().as_uri()

            for index, job in enumerate(jobs):
                job_dir = temp_root / f"job-{index}"
                job_dir.mkdir()
                command = [
                    str(self.executable),
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nofirststartwizard",
                    f"-env:UserInstallation={profile_uri}",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    str(job_dir),
                    str(job.source),
                ]
                try:
                    completed = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=180,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    results.append(
                        BackendResult(job.key, False, "LibreOffice conversion timed out")
                    )
                    continue
                except OSError as exc:
                    results.append(
                        BackendResult(job.key, False, f"could not start LibreOffice: {exc}")
                    )
                    continue

                generated = job_dir / f"{job.source.stem}.pdf"
                if completed.returncode != 0 or not generated.is_file():
                    details = completed.stderr.strip() or completed.stdout.strip()
                    results.append(
                        BackendResult(
                            job.key,
                            False,
                            details or "LibreOffice did not create a PDF",
                        )
                    )
                    continue

                job.destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(generated), str(job.destination))
                results.append(BackendResult(job.key, True))
        return results


def choose_backend(name: str) -> ConversionBackend:
    """Select a requested backend or the best available automatic backend."""

    normalized = name.casefold()
    if normalized == "word":
        if not WordBackend.available():
            raise RuntimeError("Microsoft Word backend is not available")
        return WordBackend()
    if normalized == "libreoffice":
        if not LibreOfficeBackend.available():
            raise RuntimeError("LibreOffice backend is not available")
        return LibreOfficeBackend()
    if normalized != "auto":
        raise ValueError(f"unknown backend: {name}")

    if WordBackend.available():
        return WordBackend()
    if LibreOfficeBackend.available():
        return LibreOfficeBackend()
    raise RuntimeError(
        "no conversion backend is available; install Microsoft Word on Windows "
        "or LibreOffice with soffice on PATH"
    )


def find_powershell() -> Path | None:
    """Locate Windows PowerShell without requiring it on PATH."""

    discovered = shutil.which("powershell.exe") or shutil.which("powershell")
    if discovered:
        return Path(discovered)
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = (
            Path(system_root)
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        if candidate.is_file():
            return candidate
    return None


def find_soffice() -> Path | None:
    """Locate LibreOffice on PATH or in common Windows install directories."""

    discovered = shutil.which("soffice") or shutil.which("libreoffice")
    if discovered:
        return Path(discovered)
    if os.name == "nt":
        for candidate in (
            Path("C:/Program Files/LibreOffice/program/soffice.exe"),
            Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        ):
            if candidate.is_file():
                return candidate
    return None


def word_is_registered() -> bool:
    """Check the Windows COM registry without starting Microsoft Word."""

    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            return True
    except (ImportError, OSError):
        return False


def parse_backend_payload(stdout: str) -> dict[str, object] | None:
    """Parse the compact JSON object written by the PowerShell worker."""

    content = stdout.strip().lstrip("\ufeff")
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        lines = [line.strip().lstrip("\ufeff") for line in content.splitlines() if line.strip()]
        if not lines:
            return None
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def failure_results(
    jobs: Sequence[BackendJob],
    message: str,
) -> list[BackendResult]:
    """Create a failure result for every supplied job."""

    return [BackendResult(job.key, False, message) for job in jobs]
