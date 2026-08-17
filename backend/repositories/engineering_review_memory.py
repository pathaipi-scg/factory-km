"""Thread-safe in-memory engineering repository for tests and composition."""

from dataclasses import replace
from threading import RLock

from backend.domain.engineering_review import (
    ConfirmedCommand, EngineeringReview, EngineeringReviewConcurrencyError,
    ExtractionRun, ReviewStatus,
)


class InMemoryEngineeringReviewRepository:
    def __init__(self) -> None:
        self._runs: dict[str, ExtractionRun] = {}; self._run_keys: dict[str, str] = {}
        self._reviews: dict[str, EngineeringReview] = {}; self._commands: dict[str, dict[str, ConfirmedCommand]] = {}; self._versions: dict[str, int] = {}; self._lock = RLock()

    def discover_extraction(self, run: ExtractionRun) -> ExtractionRun:
        with self._lock:
            existing_id = self._run_keys.get(run.idempotency_key)
            if existing_id: return self._runs[existing_id]
            self._runs[run.extraction_run_id] = run; self._run_keys[run.idempotency_key] = run.extraction_run_id
            return run

    def get_extraction(self, extraction_run_id: str) -> ExtractionRun | None: return self._runs.get(extraction_run_id)

    def create_review(self, review: EngineeringReview) -> EngineeringReview:
        with self._lock:
            self._versions[review.review_id] = 1; stored = replace(review, concurrency_token=self._token(1)); self._reviews[review.review_id] = stored; return stored

    def get_review(self, review_id: str) -> EngineeringReview | None: return self._reviews.get(review_id)

    def save_review(self, review: EngineeringReview, expected_token: bytes) -> EngineeringReview:
        with self._lock:
            current = self._reviews.get(review.review_id)
            if current is None or current.concurrency_token != expected_token: raise EngineeringReviewConcurrencyError("Engineering review was modified concurrently.")
            version = self._versions[review.review_id] + 1; stored = replace(review, concurrency_token=self._token(version)); self._versions[review.review_id] = version; self._reviews[review.review_id] = stored; return stored

    def confirm(self, review: EngineeringReview, commands: tuple[ConfirmedCommand, ...], expected_token: bytes) -> tuple[EngineeringReview, tuple[ConfirmedCommand, ...]]:
        with self._lock:
            current = self._reviews.get(review.review_id)
            if current and current.status is ReviewStatus.CONFIRMED: return current, self.list_commands(review.review_id)
            stored = self.save_review(review, expected_token); bucket = self._commands.setdefault(review.review_id, {})
            for command in commands: bucket.setdefault(command.idempotency_key, command)
            return stored, self.list_commands(review.review_id)

    def list_commands(self, review_id: str) -> tuple[ConfirmedCommand, ...]: return tuple(sorted(self._commands.get(review_id, {}).values(), key=lambda item: item.idempotency_key))

    @staticmethod
    def _token(version: int) -> bytes: return version.to_bytes(8, "big")
