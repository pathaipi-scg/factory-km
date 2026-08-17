"""Thread-safe in-memory engineering repository for tests and composition."""

from dataclasses import replace
from threading import RLock

from backend.domain.engineering_review import (
    CommandStatus, ConfirmedCommand, EngineeringReview, EngineeringReviewConcurrencyError,
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

    def get_command(self, command_id: str) -> ConfirmedCommand | None:
        return next((item for bucket in self._commands.values() for item in bucket.values() if item.command_id==command_id),None)

    def claim_command(self,command_id,lease_id,lease_expires_at,now):
        with self._lock:
            current=self.get_command(command_id)
            if current is None or current.status is CommandStatus.SUCCEEDED:return None
            if current.status is CommandStatus.EXECUTING and current.lease_expires_at and current.lease_expires_at>now:return None
            claimed=replace(current,status=CommandStatus.EXECUTING,attempts=current.attempts+1,lease_id=lease_id,
                            lease_expires_at=lease_expires_at,updated_at=now,last_error=None,failure_code=None)
            self._commands[current.review_id][current.idempotency_key]=claimed;return claimed

    def complete_command(self,command):
        with self._lock:
            stored=replace(command,lease_id=None,lease_expires_at=None);self._commands[command.review_id][command.idempotency_key]=stored;return stored

    def record_event(self,review_id,action,command_id=None,failure_code=None,actor_id=None):
        if not hasattr(self,"events"):self.events=[]
        self.events.append({"review_id":review_id,"action":action,"command_id":command_id,"failure_code":failure_code,"actor_id":actor_id})

    @staticmethod
    def _token(version: int) -> bytes: return version.to_bytes(8, "big")
