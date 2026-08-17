"""Trusted logical source-document content boundary for canonical execution."""

from dataclasses import dataclass
import hashlib
from typing import Protocol

from backend.services.training_service import TrainingService


class SourceDocumentProviderError(RuntimeError): pass


@dataclass(frozen=True)
class SourceDocumentContent:
    source_document_id: str
    original_filename: str
    content: bytes
    sha256: str


class SourceDocumentProvider(Protocol):
    def get(self, source_document_id: str) -> SourceDocumentContent: ...


class TrainingSourceDocumentProvider:
    def __init__(self, training_service: TrainingService) -> None: self.training_service = training_service

    def get(self, source_document_id: str) -> SourceDocumentContent:
        try:
            source_file, content = self.training_service.read_source_content(source_document_id)
        except Exception as error:
            raise SourceDocumentProviderError("Reviewed source document content is unavailable.") from error
        return SourceDocumentContent(source_document_id, source_file, content, hashlib.sha256(content).hexdigest())


class InMemorySourceDocumentProvider:
    def __init__(self, documents: dict[str, tuple[str, bytes]]) -> None: self.documents = documents
    def get(self, source_document_id: str) -> SourceDocumentContent:
        try: filename, content = self.documents[source_document_id]
        except KeyError as error: raise SourceDocumentProviderError("Reviewed source document content is unavailable.") from error
        return SourceDocumentContent(source_document_id, filename, content, hashlib.sha256(content).hexdigest())
