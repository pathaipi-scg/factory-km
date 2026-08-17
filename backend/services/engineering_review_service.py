"""Application service for persistent engineering review and READY commands."""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from backend.domain.engineering_review import (
    DecisionAction, DecisionKind, EngineeringReview, EngineeringReviewError,
    ExtractionRun, ReviewerDecision, ReviewStatus, prepare_commands,
)
from backend.repositories.engineering_review_protocols import EngineeringReviewRepository


class EngineeringReviewNotFoundError(LookupError): pass


class EngineeringReviewService:
    def __init__(self, repository: EngineeringReviewRepository) -> None: self.repository = repository

    def persist_extraction(self, snapshot: dict[str, Any], **identity: Any) -> ExtractionRun:
        classification = snapshot.get("classification", {})
        run = ExtractionRun.create(document_type=str(classification.get("document_type", "unknown")), snapshot=snapshot, **identity)
        return self.repository.discover_extraction(run)

    def create_review(self, extraction_run_id: str, actor_id: str | None = None) -> EngineeringReview:
        if self.repository.get_extraction(extraction_run_id) is None: raise EngineeringReviewNotFoundError("Extraction run was not found.")
        return self.repository.create_review(EngineeringReview.create(extraction_run_id, actor_id))

    def get(self, review_id: str) -> tuple[EngineeringReview, ExtractionRun]:
        review = self.repository.get_review(review_id)
        if review is None: raise EngineeringReviewNotFoundError("Engineering review was not found.")
        run = self.repository.get_extraction(review.extraction_run_id)
        if run is None: raise EngineeringReviewNotFoundError("Extraction run was not found.")
        return review, run

    def update(self, review_id: str, decisions: list[dict[str, Any]], kepware_paths: list[str], token: bytes) -> EngineeringReview:
        review, _ = self.get(review_id)
        parsed = tuple(ReviewerDecision(target_ref=str(item.get("target_ref", "")), kind=DecisionKind(item.get("kind")), action=DecisionAction(item.get("action")),
                                        canonical_id=item.get("canonical_id"), expected_canonical_version=item.get("expected_canonical_version"), notes=str(item.get("notes", ""))) for item in decisions)
        return self.repository.save_review(review.update(parsed, tuple(kepware_paths)), token)

    def cancel(self, review_id: str, token: bytes) -> EngineeringReview:
        review, _ = self.get(review_id)
        if review.status is ReviewStatus.CONFIRMED: raise EngineeringReviewError("Confirmed review cannot be cancelled.")
        return self.repository.save_review(replace(review, status=ReviewStatus.CANCELLED, updated_at=datetime.now(timezone.utc)), token)

    def confirm(self, review_id: str, token: bytes) -> tuple[EngineeringReview, tuple[Any, ...]]:
        review, run = self.get(review_id)
        if review.status is ReviewStatus.CONFIRMED: return review, self.repository.list_commands(review_id)
        confirmed = replace(review, status=ReviewStatus.CONFIRMED, updated_at=datetime.now(timezone.utc))
        return self.repository.confirm(confirmed, prepare_commands(confirmed, run), token)
