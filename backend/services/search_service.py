"""Folder-search context building for trained Factory KM documents."""

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _KnowledgeDocument:
    km_id: str
    source_file: str
    category: str
    machine: str
    markdown_path: str


class SearchService:
    """Build search context using a strategy selected by ``mode``."""

    def __init__(self, km_root: str | None = None) -> None:
        self._km_root = km_root or os.environ.get("KM_VAULT_ROOT", r"D:\KM\Vault")

    def build_context(self, mode: str = "folder", folder: str = "") -> str:
        """Build context for the requested search strategy.

        Only the existing folder-search strategy is implemented in this migration
        step. Enterprise search remains intentionally unimplemented.
        """
        if mode != "folder":
            raise NotImplementedError(f"Search mode is not implemented: {mode}")

        folder = folder.strip() if isinstance(folder, str) else ""
        folder = re.sub(r"^[\\/]+|[\\/]+$", "", folder)
        walk_root = self._km_root

        if folder:
            scoped = os.path.normpath(os.path.join(self._km_root, folder))
            if scoped.startswith(self._km_root) and os.path.exists(scoped):
                walk_root = scoped

        knowledge_documents: list[_KnowledgeDocument] = []
        self.walk_trained_vault(walk_root, knowledge_documents)

        candidates: list[tuple[str, dict[str, str]]] = []
        for document in knowledge_documents:
            try:
                markdown = self._read_text(document.markdown_path)
            except OSError:
                continue

            analysis = self.extract_slide_analysis(markdown)
            if not analysis:
                continue

            references = {
                "KM_ID": document.km_id,
                "Source_File": document.source_file,
                "Category": document.category,
                "Machine": document.machine,
                "Kind": "เอกสารเทรน (ฉบับเต็ม)",
            }
            candidates.append((analysis, references))

            summary_path = re.sub(r"\.md$", "_summary.md", document.markdown_path)
            if os.path.exists(summary_path):
                try:
                    summary_markdown = self._read_text(summary_path)
                except OSError:
                    summary_markdown = ""

                summary_analysis = (
                    self.extract_slide_analysis(summary_markdown)
                    if summary_markdown
                    else ""
                )
                if summary_analysis:
                    summary_references = {
                        "KM_ID": document.km_id,
                        "Source_File": document.source_file,
                        "Category": document.category,
                        "Machine": document.machine,
                        "Kind": "สรุป (summary)",
                    }
                    candidates.append((summary_analysis, summary_references))

        return "\n\n---\n\n".join(
            self._format_candidate(index, analysis, references)
            for index, (analysis, references) in enumerate(candidates, start=1)
        )

    def walk_trained_vault(
        self, directory: str, output: list[_KnowledgeDocument]
    ) -> None:
        """Collect trained KM Markdown documents recursively from a vault path."""
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
                    self.walk_trained_vault(entry_path, output)
                elif entry.is_file() and re.fullmatch(r"KM_\d{8}_\d{6}\.md", entry.name):
                    try:
                        contents = self._read_text(entry_path)
                    except OSError:
                        continue

                    if self.get_meta(contents, "Training_Status") != "Trained":
                        continue

                    output.append(
                        _KnowledgeDocument(
                            km_id=self.get_meta(contents, "KM_ID")
                            or re.sub(r"\.md$", "", entry.name),
                            source_file=self.get_meta(contents, "Source_File"),
                            category=self.get_meta(contents, "Category"),
                            machine=self.get_meta(contents, "Machine"),
                            markdown_path=entry_path,
                        )
                    )

    @staticmethod
    def get_meta(contents: str, field: str) -> str:
        """Read one metadata field using the existing Markdown format."""
        match = re.search(rf"{field} *: *(.+)$", contents, re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def extract_slide_analysis(markdown: str) -> str:
        """Return the existing English or Thai Slide Analysis section."""
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

    @staticmethod
    def _format_candidate(
        index: int, analysis: str, references: dict[str, str]
    ) -> str:
        header = (
            f"=== เอกสารที่ {index} ===\n"
            f"Source_File: {references['Source_File'] or '-'} | "
            f"ประเภท: {references['Kind'] or '-'}\n"
            f"Category: {references['Category'] or '-'} | "
            f"Machine: {references['Machine'] or '-'} | "
            f"KM_ID: {references['KM_ID'] or '-'}"
        )
        return f"{header}\n\n{analysis}"
