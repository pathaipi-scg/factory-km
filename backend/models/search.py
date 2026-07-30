"""Framework-neutral search domain contracts."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SearchRequest:
    query: str
    mode: str = "folder"
    folder: str | None = None
    filters: Mapping[str, Any] = field(default_factory=dict)
    request_context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchDocument:
    id: str
    content: str
    source_type: str = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchReference:
    document_id: str
    title: str | None = None
    source: str | None = None
    location: str | None = None
    page: int | None = None
    section: str | None = None
    citation_label: str | None = None


@dataclass(frozen=True)
class SearchHit:
    document: SearchDocument
    references: tuple[SearchReference, ...] = ()
    score: float | None = None
    strategy: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchWarning:
    code: str
    message: str
    source: str | None = None
    strategy: str | None = None


@dataclass(frozen=True)
class SearchResult:
    hits: tuple[SearchHit, ...] = ()
    warnings: tuple[SearchWarning, ...] = ()
    strategy: str | None = None
    total_hits: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
