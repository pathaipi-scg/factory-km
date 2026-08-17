"""Transactional central MSSQL repository for engineering review state."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import timezone
import json
from typing import Any, Iterator

from backend.db.engineering_mssql_migrations import apply_engineering_mssql_migrations
from backend.db.mssql import MSSQLConnectionFactory
from backend.domain.engineering_review import (
    CommandStatus, ConfirmedCommand, DecisionAction, DecisionKind, EngineeringReview,
    EngineeringReviewConcurrencyError, ExtractionRun, ExtractionRunStatus,
    ReviewerDecision, ReviewStatus,
)


class EngineeringMSSQLDatabase:
    def __init__(self, connection_factory: MSSQLConnectionFactory) -> None: self.connection_factory=connection_factory
    def initialize(self) -> None:
        with self.connect() as connection: apply_engineering_mssql_migrations(connection)
    @contextmanager
    def connect(self) -> Iterator[Any]:
        with self.connection_factory.connect() as connection: yield connection


def _naive(value): return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
def _aware(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class MSSQLEngineeringReviewRepository:
    def __init__(self,database:EngineeringMSSQLDatabase)->None:self.db=database

    def discover_extraction(self,run:ExtractionRun)->ExtractionRun:
        existing_id=None
        with self.db.connect() as connection:
            cursor=connection.cursor(); cursor.execute("SELECT ExtractionRunId FROM engineering.ExtractionRuns WITH(UPDLOCK,HOLDLOCK) WHERE IdempotencyKey=?",run.idempotency_key); row=cursor.fetchone()
            if row:existing_id=str(row[0])
            else:cursor.execute("""INSERT INTO engineering.ExtractionRuns(ExtractionRunId,StableDocumentId,DocumentVersionId,SourceDocumentId,SourceResourceId,SourceResourceVersion,SourceSha256,DocumentType,ExtractorVersion,SchemaVersion,IdempotencyKey,SnapshotJson,Status,CreatedAt) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    run.extraction_run_id,run.stable_document_id,run.document_version_id,run.source_document_id,run.source_resource_id,run.source_resource_version,run.source_sha256,run.document_type,run.extractor_version,run.schema_version,run.idempotency_key,run.snapshot_json,run.status.value,_naive(run.created_at))
        if existing_id:return self.get_extraction(existing_id) or run
        return run

    def get_extraction(self,run_id:str)->ExtractionRun|None:
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("SELECT ExtractionRunId,SourceDocumentId,SourceSha256,DocumentType,ExtractorVersion,SchemaVersion,SnapshotJson,IdempotencyKey,CreatedAt,Status,StableDocumentId,DocumentVersionId,SourceResourceId,SourceResourceVersion FROM engineering.ExtractionRuns WHERE ExtractionRunId=?",run_id); r=c.fetchone()
        return None if not r else ExtractionRun(str(r[0]),str(r[1]),str(r[2]),str(r[3]),str(r[4]),str(r[5]),str(r[6]),str(r[7]),_aware(r[8]),ExtractionRunStatus(str(r[9])),r[10],r[11],r[12],r[13])

    def create_review(self,review:EngineeringReview)->EngineeringReview:
        decisions=self._decisions(review); paths=json.dumps(review.intended_kepware_paths)
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("""INSERT INTO engineering.Reviews(ReviewId,ExtractionRunId,Status,DecisionsJson,KepwarePathsJson,ActorId,Source,CreatedAt,UpdatedAt) OUTPUT inserted.RowVersion VALUES(?,?,?,?,?,?,?,?,?)""",review.review_id,review.extraction_run_id,review.status.value,decisions,paths,review.actor_id,review.source,_naive(review.created_at),_naive(review.updated_at)); token=bytes(c.fetchone()[0]); self._event(c,review,None)
        return EngineeringReview(**{**review.__dict__,"concurrency_token":token})

    def get_review(self,review_id:str)->EngineeringReview|None:
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("SELECT ReviewId,ExtractionRunId,Status,DecisionsJson,KepwarePathsJson,CreatedAt,UpdatedAt,ActorId,Source,RowVersion FROM engineering.Reviews WHERE ReviewId=?",review_id); r=c.fetchone()
        if not r:return None
        decisions=tuple(ReviewerDecision(str(x["target_ref"]),DecisionKind(x["kind"]),DecisionAction(x["action"]),x.get("canonical_id"),x.get("expected_canonical_version"),str(x.get("notes",""))) for x in json.loads(str(r[3])))
        return EngineeringReview(str(r[0]),str(r[1]),ReviewStatus(str(r[2])),decisions,tuple(json.loads(str(r[4]))),_aware(r[5]),_aware(r[6]),r[7],str(r[8]),bytes(r[9]))

    def save_review(self,review:EngineeringReview,expected_token:bytes)->EngineeringReview:
        current=self.get_review(review.review_id)
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("""UPDATE engineering.Reviews SET Status=?,DecisionsJson=?,KepwarePathsJson=?,ActorId=?,Source=?,UpdatedAt=? OUTPUT inserted.RowVersion WHERE ReviewId=? AND RowVersion=?""",review.status.value,self._decisions(review),json.dumps(review.intended_kepware_paths),review.actor_id,review.source,_naive(review.updated_at),review.review_id,expected_token); row=c.fetchone()
            if row is None:raise EngineeringReviewConcurrencyError("Engineering review was modified concurrently.")
            self._event(c,review,current.status.value if current else None); token=bytes(row[0])
        return EngineeringReview(**{**review.__dict__,"concurrency_token":token})

    def confirm(self,review:EngineeringReview,commands:tuple[ConfirmedCommand,...],expected_token:bytes):
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("""UPDATE engineering.Reviews SET Status='confirmed',DecisionsJson=?,KepwarePathsJson=?,UpdatedAt=? OUTPUT inserted.RowVersion WHERE ReviewId=? AND RowVersion=?""",self._decisions(review),json.dumps(review.intended_kepware_paths),_naive(review.updated_at),review.review_id,expected_token); row=c.fetchone()
            if row is None:raise EngineeringReviewConcurrencyError("Engineering review was modified concurrently.")
            for x in commands:c.execute("""IF NOT EXISTS(SELECT 1 FROM engineering.Commands WHERE IdempotencyKey=?) INSERT INTO engineering.Commands(CommandId,ReviewId,CommandType,PayloadJson,IdempotencyKey,ExpectedCanonicalVersion,Status,Attempts,LastError,CreatedAt,UpdatedAt) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",x.idempotency_key,x.command_id,x.review_id,x.command_type,x.payload_json,x.idempotency_key,x.expected_canonical_version,x.status.value,x.attempts,x.last_error,_naive(x.created_at),_naive(x.updated_at))
            self._event(c,review,"in_review"); token=bytes(row[0])
        stored=EngineeringReview(**{**review.__dict__,"concurrency_token":token}); return stored,self.list_commands(review.review_id)

    def list_commands(self,review_id:str)->tuple[ConfirmedCommand,...]:
        with self.db.connect() as connection:
            c=connection.cursor(); c.execute("SELECT CommandId,ReviewId,CommandType,PayloadJson,IdempotencyKey,Status,Attempts,LastError,CreatedAt,UpdatedAt,ExpectedCanonicalVersion FROM engineering.Commands WHERE ReviewId=? ORDER BY IdempotencyKey",review_id); rows=c.fetchall()
        return tuple(ConfirmedCommand(str(r[0]),str(r[1]),str(r[2]),str(r[3]),str(r[4]),CommandStatus(str(r[5])),int(r[6]),r[7],_aware(r[8]),_aware(r[9]),r[10]) for r in rows)

    @staticmethod
    def _decisions(review):return json.dumps([{**asdict(x),"kind":x.kind.value,"action":x.action.value} for x in review.decisions],ensure_ascii=False)
    @staticmethod
    def _event(cursor,review,previous):cursor.execute("INSERT INTO engineering.ReviewEvents(ReviewId,ActionAt,ActorId,Source,PreviousState,NewState) VALUES(?,?,?,?,?,?)",review.review_id,_naive(review.updated_at),review.actor_id,review.source,previous,review.status.value)
