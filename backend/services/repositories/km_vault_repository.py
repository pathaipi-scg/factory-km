"""Filesystem repository for trained Factory KM vault records."""

import os
from pathlib import Path
import re
from dataclasses import dataclass

from backend.config.vault import VaultSettings, get_vault_settings


@dataclass(frozen=True)
class KmVaultRecord:
    """Structured trained-KM material read from the filesystem vault."""

    km_id: str
    source_file: str
    category: str
    machine: str
    markdown_path: str
    analysis: str
    summary_analysis: str | None = None


class KmVaultRepository:
    """Read trained KM records from the existing filesystem vault."""

    def __init__(self, km_root: str | None = None) -> None:
        self._vault_settings = (
            VaultSettings(Path(km_root).resolve(), explicitly_configured=True)
            if km_root is not None
            else get_vault_settings()
        )
        self._km_root = str(self._vault_settings.root)

    def list_trained(self, folder: str | None = None) -> tuple[KmVaultRecord, ...]:
        """Return trained KM records in the current filesystem traversal order."""
        self._vault_settings.require_readable()
        folder = folder.strip() if isinstance(folder, str) else ""
        folder = re.sub(r"^[\\/]+|[\\/]+$", "", folder)
        walk_root = self._km_root

        if folder:
            scoped = os.path.normpath(os.path.join(self._km_root, folder))
            if scoped.startswith(self._km_root) and os.path.exists(scoped):
                walk_root = scoped

        records: list[KmVaultRecord] = []
        self._walk_trained_vault(walk_root, records)
        return tuple(records)

    def _walk_trained_vault(
        self, directory: str, output: list[KmVaultRecord]
    ) -> None:
        try:
            entries = os.scandir(directory)
        except OSError:
            return

        with entries:
            for entry in entries:
                entry_path = entry.path
                if entry.is_dir():
                    if re.fullmatch(r"KM_\d{8}_\d{6}", entry.name):
                        continue
                    if entry.name == ".obsidian":
                        continue
                    self._walk_trained_vault(entry_path, output)
                elif entry.is_file() and re.fullmatch(
                    r"KM_\d{8}_\d{6}\.md", entry.name
                ):
                    try:
                        markdown = self._read_text(entry_path)
                    except OSError:
                        continue

                    if self._get_meta(markdown, "Training_Status") != "Trained":
                        continue

                    analysis = self._extract_slide_analysis(markdown)
                    if not analysis:
                        continue

                    summary_analysis = self._load_summary(entry_path)
                    output.append(
                        KmVaultRecord(
                            km_id=self._get_meta(markdown, "KM_ID")
                            or re.sub(r"\.md$", "", entry.name),
                            source_file=self._get_meta(markdown, "Source_File"),
                            category=self._get_meta(markdown, "Category"),
                            machine=self._get_meta(markdown, "Machine"),
                            markdown_path=entry_path,
                            analysis=analysis,
                            summary_analysis=summary_analysis,
                        )
                    )

    def _load_summary(self, markdown_path: str) -> str | None:
        summary_path = re.sub(r"\.md$", "_summary.md", markdown_path)
        if not os.path.exists(summary_path):
            return None

        try:
            summary_markdown = self._read_text(summary_path)
        except OSError:
            summary_markdown = ""

        summary_analysis = (
            self._extract_slide_analysis(summary_markdown)
            if summary_markdown
            else ""
        )
        return summary_analysis or None

    @staticmethod
    def _get_meta(markdown: str, field: str) -> str:
        match = re.search(rf"{field} *: *(.+)$", markdown, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_slide_analysis(markdown: str) -> str:
        match = re.search(r"^# Slide Analysis\s*$", markdown, re.MULTILINE)
        if not match:
            match = re.search(
                r"^# การวิเคราะห์สไลด์\s*$", markdown, re.MULTILINE
            )
        return markdown[match.start() :].strip() if match else ""

    @staticmethod
    def _read_text(path: str) -> str:
        with open(path, encoding="utf-8") as file:
            return file.read()
