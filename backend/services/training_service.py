"""Factory-KM Office conversion and direct vision-training workflow."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.config.azure_openai import AzureOpenAISettings
from backend.config.vault import VaultConfigurationError, VaultSettings, get_vault_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KM_NAME = re.compile(r"^KM_\d{8}_\d{6}$")
SLIDE_NAME = re.compile(r"^Slide\d{3}\.png$")
CONVERTERS = {
    ".ppt": "ppt_to_png.py",
    ".pptx": "ppt_to_png.py",
    ".xls": "excel_to_png.py",
    ".xlsx": "excel_to_png.py",
    ".pdf": "pdf_to_png.py",
    ".doc": "docx_to_png.py",
    ".docx": "docx_to_png.py",
}


class TrainingError(RuntimeError):
    """A safe, user-facing training failure."""


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content: bytes


@dataclass(frozen=True)
class CreatedKm:
    km_id: str
    source_file: str
    source_path: Path
    asset_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class TrainedKmInput:
    """Completed Training output consumed by downstream extraction."""
    source_document_id: str
    source_file: str
    source_content_sha256: str
    detail_markdown: str
    summary_markdown: str


def _timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")


def _km_id(value: datetime) -> str:
    return value.strftime("KM_%Y%m%d_%H%M%S")


def _metadata_value(markdown: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}\s*:\s*(.*)$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _replace_metadata(markdown: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}\s*:\s*.*$", re.MULTILINE)
    replacement = f"{key} : {value}"
    return pattern.sub(replacement, markdown, count=1) if pattern.search(markdown) else markdown


def _slides(asset_path: Path) -> list[Path]:
    if not asset_path.is_dir():
        return []
    return sorted(path for path in asset_path.iterdir() if SLIDE_NAME.fullmatch(path.name))


def _safe_converter_error(value: object) -> str:
    """Keep a useful converter reason while redacting common secret assignments."""
    text = str(value or "converter produced zero or mismatched pages")
    text = re.sub(
        r"(?i)(api[-_ ]?key|password|secret|token)\s*[:=]\s*\S+",
        r"\1=[redacted]",
        text,
    )
    return text[:500]


def build_metadata(
    *, km_id: str, source_file: str, target_path: str, category: str,
    machine: str, status: str, slide_count: int, png_count: int,
    converted_at: str, duration_seconds: int, created_at: str,
) -> str:
    """Build the legacy-compatible Factory-KM detail Markdown header."""
    markdown = f"""# KM Information
KM_ID : {km_id}
Source_File : {source_file}
Target_Path : {target_path}
Category : {category}
Machine : {machine}
Status : Active
Version : 1
Processing_Status : {status}
Slide_Count : {slide_count}
PNG_Count : {png_count}
Converted_At : {converted_at}
Conversion_Duration_Sec : {duration_seconds if status == 'Converted' else 0}
Asset_Folder : {km_id}
Created : {created_at}
Training_Status : NotTrained
Training_Date :
Training_Model :
Training_Slides : 0
Training_Progress : 0
Training_Version : 0
"""
    if status == "Converted" and png_count > 0:
        markdown += "\n# Slides\n"
        for index in range(1, png_count + 1):
            markdown += f"![[{km_id}/Slide{index:03d}.png]]\n\n"
    return markdown


class AzureTrainingClient:
    """Direct Azure OpenAI vision and summary calls for Training only."""

    SLIDE_PROMPT = (
        "Analyze this slide. Return markdown format. Explain: Slide title, Purpose, "
        "Equipment, Process flow, Important observations, Root cause, Countermeasure. "
        "Use Thai language."
    )
    SUMMARY_PROMPT = (
        "Summarize this trained engineering document in concise Markdown. Include the "
        "document purpose, major equipment, processes, keywords, failures, alarms, and "
        "troubleshooting topics. Use Thai language."
    )

    def __init__(self, settings: AzureOpenAISettings | None = None) -> None:
        self.settings = settings or AzureOpenAISettings.from_environment()

    def analyze_slide(self, image_path: Path) -> str:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return self._call([
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": self.SLIDE_PROMPT},
                    {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
                ],
            }
        ])

    def summarize(self, analysis: str) -> str:
        return self._call(f"{self.SUMMARY_PROMPT}\n\n{analysis}")

    def _call(self, input_value: object) -> str:
        payload = json.dumps({"model": self.settings.deployment, "input": input_value}).encode()
        request = Request(
            self.settings.responses_url,
            data=payload,
            method="POST",
            headers={"api-key": self.settings.api_key, "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise TrainingError(f"Azure OpenAI returned HTTP {error.code}") from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise TrainingError("Azure OpenAI request failed") from error
        for output in result.get("output", []):
            if not isinstance(output, dict):
                continue
            for content in output.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    text = content["text"].strip()
                    if text:
                        return text
        raise TrainingError("Azure OpenAI response did not contain text")


class TrainingService:
    """Preserve the server.js Training behavior behind FastAPI endpoints."""

    def __init__(
        self,
        vault_root: Path | None = None,
        python_bin: str | None = None,
        vision_client: AzureTrainingClient | None = None,
        converter_runner: Callable[[Path, Path, Path], dict[str, object]] | None = None,
    ) -> None:
        self.vault_settings = (
            VaultSettings(Path(vault_root).resolve(), explicitly_configured=True)
            if vault_root is not None
            else get_vault_settings()
        )
        self.vault_root = self.vault_settings.root
        self.python_bin = python_bin or os.environ.get("PYTHON_BIN", sys.executable)
        self.vision_client = vision_client
        self.converter_runner = converter_runner or self._run_converter

    @staticmethod
    def sanitize_target_path(target_path: str) -> str:
        normalized = target_path.replace("\\", "/").strip("/")
        parts = [part for part in normalized.split("/") if part]
        if not parts or any(part in {".", ".."} or "\x00" in part for part in parts):
            raise TrainingError("Invalid targetPath")
        return "/".join(parts)

    def upload(
        self,
        files: Iterable[UploadedFile],
        target_path: str,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> list[CreatedKm]:
        try:
            self.vault_settings.require_writable()
        except VaultConfigurationError as error:
            raise TrainingError(str(error)) from error
        clean_target = self.sanitize_target_path(target_path)
        destination = (self.vault_root / Path(*clean_target.split("/"))).resolve()
        try:
            destination.relative_to(self.vault_root)
        except ValueError as error:
            raise TrainingError("Invalid targetPath") from error
        items = list(files)
        if not items:
            raise TrainingError("No files uploaded")
        destination.mkdir(parents=True, exist_ok=True)
        segments = clean_target.split("/")
        category, machine = segments[0], segments[-1]
        created_at = _timestamp()
        next_time = datetime.now()
        created: list[CreatedKm] = []
        total = len(items)
        for item_index, item in enumerate(items):
            safe_name = Path(item.filename.replace("\\", "/")).name
            if not safe_name:
                raise TrainingError("Uploaded file has no filename")
            if progress:
                progress(item_index, total, safe_name)
            while (destination / f"{_km_id(next_time)}.md").exists():
                next_time = datetime.fromtimestamp(next_time.timestamp() + 1)
            km_id = _km_id(next_time)
            next_time = datetime.fromtimestamp(next_time.timestamp() + 1)
            source_path = destination / safe_name
            asset_path = destination / km_id
            markdown_path = destination / f"{km_id}.md"
            source_path.write_bytes(item.content)
            asset_path.mkdir(parents=True, exist_ok=True)
            base = dict(
                km_id=km_id, source_file=safe_name, target_path=clean_target,
                category=category, machine=machine, created_at=created_at,
            )
            markdown_path.write_text(build_metadata(
                **base, status="Uploaded", slide_count=0, png_count=0,
                converted_at="", duration_seconds=0,
            ), encoding="utf-8")
            record = CreatedKm(km_id, safe_name, source_path, asset_path, markdown_path)
            created.append(record)
            converter_name = CONVERTERS.get(source_path.suffix.lower())
            if not converter_name:
                markdown_path.write_text(build_metadata(
                    **base, status="ConversionFailed", slide_count=0, png_count=0,
                    converted_at="", duration_seconds=0,
                ), encoding="utf-8")
                raise TrainingError(f"Unsupported file type: {source_path.suffix.lower() or '(none)'}")
            script = PROJECT_ROOT / "assets" / "python" / converter_name
            started = time.monotonic()
            result: dict[str, object] = {}
            for attempt in range(3):
                for slide in _slides(asset_path):
                    slide.unlink(missing_ok=True)
                try:
                    result = self.converter_runner(script, source_path, asset_path)
                except Exception as error:
                    result = {
                        "success": False,
                        "error": f"{type(error).__name__}: {_safe_converter_error(error)}",
                    }
                try:
                    count = int(result.get("slideCount") or result.get("sheetCount") or 0)
                except (TypeError, ValueError):
                    count = 0
                png_count = len(_slides(asset_path))
                if result.get("success") is True and count > 0 and png_count > 0 and count == png_count:
                    markdown_path.write_text(build_metadata(
                        **base, status="Converted", slide_count=count, png_count=png_count,
                        converted_at=_timestamp(), duration_seconds=round(time.monotonic() - started),
                    ), encoding="utf-8")
                    break
                if attempt < 2:
                    time.sleep(1.5)
            else:
                for slide in _slides(asset_path):
                    slide.unlink(missing_ok=True)
                markdown_path.write_text(build_metadata(
                    **base, status="ConversionFailed", slide_count=0, png_count=0,
                    converted_at="", duration_seconds=0,
                ), encoding="utf-8")
                reason = _safe_converter_error(result.get("error"))
                raise TrainingError(f"Conversion failed for {safe_name}: {reason}")
            if progress:
                progress(item_index + 1, total, safe_name)
        return created

    def _run_converter(self, script: Path, source: Path, assets: Path) -> dict[str, object]:
        try:
            process = subprocess.run(
                [self.python_bin, str(script), str(source), str(assets)],
                capture_output=True, text=True, timeout=360,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise TrainingError(f"Converter could not run: {type(error).__name__}") from error
        try:
            result = json.loads(process.stdout.strip())
        except json.JSONDecodeError as error:
            raise TrainingError("Converter returned an invalid response") from error
        if not isinstance(result, dict):
            raise TrainingError("Converter returned an invalid response")
        return result

    def list_not_trained(self) -> list[dict[str, object]]:
        try:
            self.vault_settings.require_readable()
        except VaultConfigurationError as error:
            raise TrainingError(str(error)) from error
        output: list[dict[str, object]] = []
        if not self.vault_root.is_dir():
            return output
        for path in self.vault_root.rglob("KM_????????_??????.md"):
            if any(KM_NAME.fullmatch(parent.name) for parent in path.parents):
                continue
            try:
                markdown = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if _metadata_value(markdown, "Training_Status") != "NotTrained":
                continue
            raw_count = _metadata_value(markdown, "Slide_Count")
            try:
                count = int(raw_count)
            except ValueError:
                count = 0
            output.append({
                "kmId": _metadata_value(markdown, "KM_ID") or path.stem,
                "sourceFile": _metadata_value(markdown, "Source_File"),
                "category": _metadata_value(markdown, "Category"),
                "machine": _metadata_value(markdown, "Machine"),
                "slideCount": count,
                "mdPath": str(path),
            })
        return output

    def list_trained(self) -> list[dict[str, object]]:
        """List completed detail Markdown packages available for extraction."""
        try: self.vault_settings.require_readable()
        except VaultConfigurationError as error: raise TrainingError(str(error)) from error
        output: list[dict[str, object]] = []
        for path in self.vault_root.rglob("KM_????????_??????.md") if self.vault_root.is_dir() else []:
            if any(KM_NAME.fullmatch(parent.name) for parent in path.parents): continue
            try: markdown = path.read_text(encoding="utf-8")
            except OSError: continue
            if _metadata_value(markdown, "Training_Status") != "Trained" or not path.with_name(f"{path.stem}_summary.md").is_file(): continue
            output.append({"kmId": _metadata_value(markdown, "KM_ID") or path.stem,
                           "sourceFile": _metadata_value(markdown, "Source_File"),
                           "category": _metadata_value(markdown, "Category"), "machine": _metadata_value(markdown, "Machine")})
        return sorted(output, key=lambda item: str(item["kmId"]), reverse=True)

    def train_one(self, km_id: str, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        try:
            self.vault_settings.require_writable()
        except VaultConfigurationError as error:
            raise TrainingError(str(error)) from error
        markdown_path = self._find_markdown(km_id)
        markdown = markdown_path.read_text(encoding="utf-8")
        asset_name = _metadata_value(markdown, "Asset_Folder")
        asset_path = markdown_path.parent / asset_name
        slides = _slides(asset_path)
        if not slides:
            self._mark_training_failure(markdown_path, markdown, "No Slide PNG")
            raise TrainingError(f"{km_id}: No Slide PNG")
        client = self.vision_client or AzureTrainingClient()
        analyses: list[str] = [""] * len(slides)
        try:
            # Match the legacy flow: analyze at most five slides concurrently,
            # report each completion, and retain deterministic slide ordering.
            for batch_start in range(0, len(slides), 5):
                batch = slides[batch_start:batch_start + 5]
                batch_error: Exception | None = None
                with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                    futures = {
                        executor.submit(client.analyze_slide, slide): batch_start + offset
                        for offset, slide in enumerate(batch)
                    }
                    for future in as_completed(futures):
                        index = futures[future]
                        try:
                            analyses[index] = future.result()
                        except Exception as error:
                            batch_error = batch_error or error
                        if progress:
                            progress(_metadata_value(markdown, "Source_File"))
                if batch_error:
                    raise batch_error
            analysis = "\n\n".join(
                f"## Slide {index}\n{text}" for index, text in enumerate(analyses, 1)
            )
            summary = client.summarize(analysis)
        except Exception as error:
            safe_error = error if isinstance(error, TrainingError) else TrainingError(type(error).__name__)
            self._mark_training_failure(markdown_path, markdown, str(safe_error))
            raise safe_error
        detail = re.sub(r"\n# Slide Analysis[\s\S]*$", "", markdown).rstrip()
        detail += f"\n\n# Slide Analysis\n\n{analysis}\n"
        detail = _replace_metadata(detail, "Training_Status", "Trained")
        detail = _replace_metadata(detail, "Training_Date", _timestamp())
        detail = _replace_metadata(detail, "Training_Model", client.settings.deployment if isinstance(client, AzureTrainingClient) else "configured")
        detail = _replace_metadata(detail, "Training_Slides", str(len(slides)))
        detail = _replace_metadata(detail, "Training_Progress", "100")
        header = re.split(r"\n# Slides|\n# Slide Analysis", detail, maxsplit=1)[0].rstrip()
        summary_path = markdown_path.with_name(f"{markdown_path.stem}_summary.md")
        try:
            # Training is only successful after both artifacts exist. Write the
            # summary first and make the detail's Trained status the final step.
            summary_path.write_text(
                f"{header}\n\n# Slide Analysis\n\n{summary.strip()}\n", encoding="utf-8"
            )
            markdown_path.write_text(detail, encoding="utf-8")
        except OSError as error:
            self._mark_training_failure(markdown_path, markdown, "Unable to write training output")
            raise TrainingError("Unable to write training output") from error
        return {"kmId": km_id, "updated": True, "slideCount": len(slides), "success": True}

    def slide_count(self, km_id: str) -> int:
        """Return the actual asset count used by training progress."""
        path = self._find_markdown(km_id)
        markdown = path.read_text(encoding="utf-8")
        return len(_slides(path.parent / _metadata_value(markdown, "Asset_Folder")))

    def read_trained_input(self, km_id: str) -> TrainedKmInput:
        """Read the completed detail/summary pair at the post-Training hook."""
        path = self._find_markdown(km_id)
        detail = path.read_text(encoding="utf-8")
        if _metadata_value(detail, "Training_Status") != "Trained":
            raise TrainingError(f"{km_id}: KM is not successfully trained")
        summary_path = path.with_name(f"{path.stem}_summary.md")
        if not summary_path.is_file(): raise TrainingError(f"{km_id}: summary Markdown not found")
        source_file = _metadata_value(detail, "Source_File")
        source_path = path.parent / source_file
        if not source_path.is_file(): raise TrainingError(f"{km_id}: source document not found")
        return TrainedKmInput(km_id, source_file, hashlib.sha256(source_path.read_bytes()).hexdigest(),
                              detail, summary_path.read_text(encoding="utf-8"))

    def _find_markdown(self, km_id: str) -> Path:
        if not KM_NAME.fullmatch(km_id):
            raise TrainingError("Invalid kmId")
        matches = [path for path in self.vault_root.rglob(f"{km_id}.md") if path.is_file()]
        if len(matches) != 1:
            raise TrainingError(f"{km_id}: KM markdown not found" if not matches else f"{km_id}: duplicate KM markdown")
        return matches[0]

    @staticmethod
    def _mark_training_failure(path: Path, markdown: str, reason: str) -> None:
        output = re.sub(r"\n# Slide Analysis[\s\S]*$", "", markdown).rstrip()
        output += f"\n\n# Slide Analysis\n\n**[Error: {reason}]**\n"
        output = _replace_metadata(output, "Training_Status", "TrainingError")
        output = _replace_metadata(output, "Training_Date", _timestamp())
        output = _replace_metadata(output, "Training_Slides", "0")
        output = _replace_metadata(output, "Training_Progress", "0")
        path.write_text(output, encoding="utf-8")
