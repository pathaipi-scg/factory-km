"""Folder-scoped KM vault search strategy."""

from backend.models.search import (
    SearchDocument,
    SearchHit,
    SearchReference,
    SearchRequest,
    SearchResult,
    SearchWarning,
)
from backend.services.repositories.km_vault_repository import (
    KmVaultRecord,
    KmVaultRepository,
)


class FolderSearchStrategy:
    """Return trained KM vault material as normalized search results."""

    def __init__(self, repository: KmVaultRepository) -> None:
        self._repository = repository

    def search(self, request: SearchRequest) -> SearchResult:
        """Search the existing trained-KM vault using its folder behavior."""
        records = self._repository.list_trained(folder=request.folder)
        hits: list[SearchHit] = []
        warnings: list[SearchWarning] = []

        if not request.query.strip():
            warnings.append(
                SearchWarning(
                    code="empty_query",
                    message="The current Folder Search accepts an empty query.",
                    strategy="folder",
                )
            )

        for record in records:
            hits.append(self._to_hit(record, kind="full", folder=request.folder))
            if record.summary_analysis:
                hits.append(
                    self._to_hit(record, kind="summary", folder=request.folder)
                )

        if not hits:
            warnings.append(
                SearchWarning(
                    code="no_trained_documents",
                    message="No trained KM documents were found.",
                    source="km_vault",
                    strategy="folder",
                )
            )

        return SearchResult(
            hits=tuple(hits),
            warnings=tuple(warnings),
            strategy="folder",
            total_hits=len(hits),
            metadata={"mode": "folder", "folder": request.folder},
        )

    @staticmethod
    def _to_hit(
        record: KmVaultRecord, *, kind: str, folder: str | None
    ) -> SearchHit:
        is_summary = kind == "summary"
        document_id = f"{record.km_id}:summary" if is_summary else record.km_id
        analysis = record.summary_analysis if is_summary else record.analysis
        document = SearchDocument(
            id=document_id,
            content=analysis or "",
            source_type="km_vault_summary" if is_summary else "km_vault",
            metadata={
                "km_id": record.km_id,
                "folder": folder,
                "file_path": record.markdown_path,
                "title": record.source_file or record.km_id,
                "source_file": record.source_file,
                "category": record.category,
                "machine": record.machine,
                "training_status": "Trained",
                "analysis_language": FolderSearchStrategy._analysis_language(
                    analysis or ""
                ),
                "kind": kind,
            },
        )
        reference = SearchReference(
            document_id=document_id,
            title=record.source_file or record.km_id,
            source=record.source_file or None,
            location=record.markdown_path,
            section="Slide Analysis",
            citation_label=record.source_file or record.km_id,
        )
        return SearchHit(
            document=document,
            references=(reference,),
            strategy="folder",
            metadata={"km_id": record.km_id, "kind": kind},
        )

    @staticmethod
    def _analysis_language(analysis: str) -> str | None:
        if analysis.startswith("# Slide Analysis"):
            return "english"
        if analysis.startswith("# การวิเคราะห์สไลด์"):
            return "thai"
        return None
