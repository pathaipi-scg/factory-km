"""Manifest-driven PageIndex discovery without workspace generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.domain.manifest import ManifestRecord, PageIndexState
from backend.repositories.manifest import (
    ManifestConcurrencyError,
    PageIndexDiscoveryRepository,
)


class DiscoveryReason(str, Enum):
    NEW_OR_CHANGED = "new_or_changed"
    RETRY_FAILED = "retry_failed"
    RESUME_PENDING = "resume_pending"
    MISSING_WORKSPACE_MAPPING = "missing_workspace_mapping"


@dataclass(frozen=True)
class DiscoveryCandidate:
    record: ManifestRecord
    reason: DiscoveryReason


@dataclass(frozen=True)
class DiscoveryPreparation:
    candidates: tuple[DiscoveryCandidate, ...]
    ready: tuple[ManifestRecord, ...]
    conflicts: tuple[str, ...]


class PageIndexDiscoveryService:
    """Select and queue eligible Manifest versions for a future generator."""

    def __init__(self, repository: PageIndexDiscoveryRepository) -> None:
        self._repository = repository

    def scan(self) -> tuple[DiscoveryCandidate, ...]:
        eligible = {
            str(item.document_version_id): item
            for item in self._repository.list_active_trained_markdown()
            if item.eligible_for_pageindex
        }
        missing = {
            str(item.document_version_id)
            for item in self._repository.list_missing_workspace_mapping()
        }
        candidates: list[DiscoveryCandidate] = []
        for version_id in sorted(eligible):
            item = eligible[version_id]
            reason: DiscoveryReason | None = None
            if item.pageindex_state is PageIndexState.PENDING:
                reason = DiscoveryReason.RESUME_PENDING
            elif item.pageindex_state is PageIndexState.FAILED:
                reason = DiscoveryReason.RETRY_FAILED
            elif item.pageindex_state is PageIndexState.NOT_INDEXED:
                reason = DiscoveryReason.NEW_OR_CHANGED
            elif version_id in missing:
                reason = DiscoveryReason.MISSING_WORKSPACE_MAPPING
            if reason is not None:
                candidates.append(DiscoveryCandidate(item, reason))
        return tuple(candidates)

    def prepare(self) -> DiscoveryPreparation:
        """Queue new/retry/missing work; preserve already-pending resume work."""
        candidates = self.scan()
        ready: list[ManifestRecord] = []
        conflicts: list[str] = []
        for candidate in candidates:
            item = candidate.record
            version_id = str(item.document_version_id)
            if candidate.reason is DiscoveryReason.RESUME_PENDING:
                ready.append(item)
                continue
            if item.concurrency_token is None:
                conflicts.append(version_id)
                continue
            try:
                ready.append(
                    self._repository.mark_indexing_attempt(
                        version_id, item.concurrency_token
                    )
                )
            except ManifestConcurrencyError:
                conflicts.append(version_id)
        return DiscoveryPreparation(candidates, tuple(ready), tuple(conflicts))
