"""Allowlisted, revision-aware execution of confirmed engineering commands."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json, uuid
from typing import Any
from backend.config.engineering_execution import EngineeringExecutionSettings
from backend.domain.engineering_review import CommandStatus, ReviewStatus
from backend.services.engineering_review_service import EngineeringReviewNotFoundError
from backend.services.opc_tag_manager_client import OpcTagManagerClientError
from backend.services.source_document_provider import SourceDocumentProviderError

ALLOWLIST={"UseExistingSupplier","UseExistingContact","UseExistingEquipmentPart","EnsureCanonicalDocumentResource","LinkResourceToSupplier","LinkResourceToEquipmentPart","LinkEquipmentPartToTag","LinkResourceToTag"}
BLOCKED_PREFIXES=("ProposeCreate","ProposeUpdate","Unlink","Delete","Retire","Merge","Replace")
ORDER={"UseExistingSupplier":1,"UseExistingContact":1,"UseExistingEquipmentPart":1,"EnsureCanonicalDocumentResource":2,"LinkResourceToSupplier":3,"LinkResourceToEquipmentPart":4,"LinkEquipmentPartToTag":5,"LinkResourceToTag":6}
TYPE_MAP={"quotation":"Quotation","manual":"Manual","drawing":"Drawing","general_document":"GeneralDocument"}
class EngineeringExecutionError(RuntimeError):pass
class EngineeringExecutionDisabledError(EngineeringExecutionError):pass

@dataclass(frozen=True)
class PreflightResult:
    command_id:str;command_type:str;outcome:str;code:str;message:str;expected_operation:str|None=None;details:dict[str,Any]|None=None

class EngineeringExecutionService:
    def __init__(self,repository,client,source_documents,settings=None,clock=None):
        self.repository=repository;self.client=client;self.source_documents=source_documents;self.settings=settings or EngineeringExecutionSettings.from_environment();self.clock=clock or (lambda:datetime.now(timezone.utc))
    def dry_run(self,review_id):
        review=self._confirmed(review_id);results=[self._preflight(x,{},True) for x in self._ordered(review_id,True)]
        self.repository.record_event(review_id,"ExecutionDryRun",actor_id=review.actor_id)
        return {"review_id":review_id,"write_enabled":self.settings.write_enabled,"results":[x.__dict__ for x in results],"clean":all(x.outcome=="PASS" for x in results)}
    def execute(self,review_id):
        if not self.settings.write_enabled:raise EngineeringExecutionDisabledError("Canonical execution is disabled by configuration.")
        review=self._confirmed(review_id);resolved=self._resolved(review_id)
        # A review containing a known blocked/invalid/conflicting command must
        # not partially mutate earlier dependencies merely because of ordering.
        initial=[(command,self._preflight(command,resolved,True)) for command in self._ordered(review_id)]
        rejected=next(((command,check) for command,check in initial if check.outcome!="PASS"),None)
        if rejected:
            command,check=rejected;now=self.clock();claimed=self.repository.claim_command(command.command_id,uuid.uuid4().hex,now+timedelta(seconds=self.settings.lease_seconds),now)
            if claimed:
                status=CommandStatus.CONFLICT if check.outcome=="CONFLICT" else CommandStatus.BLOCKED if check.outcome=="BLOCKED" else CommandStatus.FAILED
                self._finish(claimed,status,check.code,{"preflight":check.__dict__},False);self.repository.record_event(review_id,"ExecutionStopped",claimed.command_id,check.code,review.actor_id)
            return self.status(review_id)
        for command in self._ordered(review_id):
            now=self.clock();claimed=self.repository.claim_command(command.command_id,uuid.uuid4().hex,now+timedelta(seconds=self.settings.lease_seconds),now)
            if claimed is None:continue
            self.repository.record_event(review_id,"CommandClaimed",claimed.command_id,actor_id=review.actor_id)
            check=self._preflight(claimed,resolved,False)
            if check.outcome!="PASS":
                status=CommandStatus.CONFLICT if check.outcome=="CONFLICT" else CommandStatus.BLOCKED if check.outcome=="BLOCKED" else CommandStatus.FAILED;self._finish(claimed,status,check.code,{"preflight":check.__dict__},False)
                self.repository.record_event(review_id,"CommandConflict" if status is CommandStatus.CONFLICT else "CommandFailed",claimed.command_id,check.code,review.actor_id);self.repository.record_event(review_id,"ExecutionStopped",claimed.command_id,check.code,review.actor_id);break
            self.repository.record_event(review_id,"CommandPreflightPassed",claimed.command_id,actor_id=review.actor_id)
            try:
                remote=self._mutate(claimed,resolved,review_id)
                if remote.get("status")=="similar_resource_found":
                    self._finish(claimed,CommandStatus.CONFLICT,"resource_similarity_decision_required",remote,False);self.repository.record_event(review_id,"CommandConflict",claimed.command_id,"resource_similarity_decision_required",review.actor_id);break
                self._finish(claimed,CommandStatus.SUCCEEDED,None,remote,False);resolved[claimed.command_id]=remote;self.repository.record_event(review_id,"CommandSucceeded",claimed.command_id,actor_id=review.actor_id)
            except OpcTagManagerClientError as error:
                code="remote_transport" if error.retriable else "remote_validation";self._finish(claimed,CommandStatus.FAILED,code,{"message":str(error)},error.retriable);self.repository.record_event(review_id,"CommandFailed",claimed.command_id,code,review.actor_id);break
        return self.status(review_id)
    def status(self,review_id):
        self._confirmed(review_id);return {"review_id":review_id,"write_enabled":self.settings.write_enabled,"commands":[self._json(x) for x in self._ordered(review_id,True)]}
    def _confirmed(self,review_id):
        review=self.repository.get_review(review_id)
        if review is None:raise EngineeringReviewNotFoundError("Engineering review was not found.")
        if review.status is not ReviewStatus.CONFIRMED:raise EngineeringExecutionError("Only a confirmed review can be executed.")
        return review
    def _preflight(self,c,resolved,dry_run):
        k=c.command_type;p=c.payload
        if k.startswith(BLOCKED_PREFIXES):return PreflightResult(c.command_id,k,"BLOCKED","future_master_data_phase","Requires future master-data approval phase.")
        if k not in ALLOWLIST:return PreflightResult(c.command_id,k,"INVALID","command_not_allowlisted","Command is not allowlisted.")
        try:
            if k=="EnsureCanonicalDocumentResource":
                source=self.source_documents.get(p["source_document_id"])
                if source.sha256!=p.get("source_sha256"):return PreflightResult(c.command_id,k,"CONFLICT","source_sha_mismatch","Trusted source bytes differ from reviewed SHA-256.")
                if p.get("document_type") not in TYPE_MAP:return PreflightResult(c.command_id,k,"INVALID","unsupported_document_type","Document type is not canonicalizable.")
            elif k=="LinkEquipmentPartToTag":
                mismatch=self._canonical(p.get("equipment_part_id"),c.expected_canonical_version)
                if mismatch:return PreflightResult(c.command_id,k,*mismatch)
                tags=self.client.search_opc_tags(p.get("kepware_path",""),100,True);exact=[x for x in tags if x.get("kepware_path")==p.get("kepware_path")]
                if not exact or not exact[0].get("is_active"):return PreflightResult(c.command_id,k,"CONFLICT","kepware_path_missing_or_inactive","Exact active KepwarePath was not found.")
            else:
                identity=p.get("canonical_id") or p.get("supplier_id") or p.get("equipment_part_id")
                if identity:
                    mismatch=self._canonical(identity,c.expected_canonical_version)
                    if mismatch:return PreflightResult(c.command_id,k,*mismatch)
                if p.get("source_resource_id"):
                    state=self.client.get_canonical_state(p["source_resource_id"])
                    if not state.get("exists"):return PreflightResult(c.command_id,k,"CONFLICT","source_resource_missing","Source Resource no longer exists.")
                if p.get("source_command_id") and not dry_run and p["source_command_id"] not in resolved:return PreflightResult(c.command_id,k,"INVALID","dependency_not_succeeded","Canonical document prerequisite has not succeeded.")
            return PreflightResult(c.command_id,k,"PASS","preflight_passed","Preflight passed.",k)
        except (KeyError,TypeError,ValueError,SourceDocumentProviderError) as error:return PreflightResult(c.command_id,k,"INVALID","invalid_command_payload",str(error))
        except OpcTagManagerClientError as error:return PreflightResult(c.command_id,k,"CONFLICT" if error.retriable else "INVALID","remote_preflight_failed",str(error))
    def _canonical(self,identity,expected):
        state=self.client.get_canonical_state(identity)
        if not state.get("exists"):return("CONFLICT","canonical_missing","Canonical identity no longer exists.")
        current=state.get("supplier_canonical_revision") if str(identity).startswith("CNT_") else state.get("canonical_revision")
        if not expected:return("INVALID","expected_revision_missing","Reviewed canonical revision is missing.")
        if current!=expected:return("CONFLICT","canonical_revision_mismatch","Canonical state changed after review.")
    def _mutate(self,c,resolved,review_id):
        p=c.payload;k=c.command_type
        if k.startswith("UseExisting"):return{"status":"validated","canonical_id":p["canonical_id"],"canonical_revision":c.expected_canonical_version}
        if k=="EnsureCanonicalDocumentResource":
            source=self.source_documents.get(p["source_document_id"]);return self.client.create_canonical_resource(resource_type=TYPE_MAP[p["document_type"]],display_name=source.original_filename,source_sha256=source.sha256,source_document_id=source.source_document_id,original_filename=source.original_filename,content=source.content,extraction_run_id=p.get("extraction_run_id"),review_id=review_id)
        if k=="LinkEquipmentPartToTag":return self.client.link_tag_resource(p["kepware_path"],p["equipment_part_id"])
        source=p.get("source_resource_id") or resolved[p["source_command_id"]]["resource_id"]
        if k=="LinkResourceToSupplier":return self.client.link_resource_relationship(p["supplier_id"],source)
        if k=="LinkResourceToEquipmentPart":return self.client.link_resource_relationship(p["equipment_part_id"],source)
        if k=="LinkResourceToTag":return self.client.link_tag_resource(p["kepware_path"],source)
        raise EngineeringExecutionError("Command mutation is not allowlisted.")
    def _finish(self,c,status,code,result,retriable):
        value=replace(c,status=status,updated_at=self.clock(),result_json=json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")),failure_code=code,last_error=None if status is CommandStatus.SUCCEEDED else code,retriable=retriable);return self.repository.complete_command(value)
    def _ordered(self,review_id,all_status=False):
        values=self.repository.list_commands(review_id)
        if not all_status:values=tuple(x for x in values if x.status is not CommandStatus.SUCCEEDED)
        return tuple(sorted(values,key=lambda x:(ORDER.get(x.command_type,99),x.idempotency_key)))
    def _resolved(self,review_id):return{x.command_id:x.result for x in self.repository.list_commands(review_id) if x.status is CommandStatus.SUCCEEDED and x.result}
    @staticmethod
    def _json(x):return{"command_id":x.command_id,"command_type":x.command_type,"status":x.status.value,"attempts":x.attempts,"failure_code":x.failure_code,"retriable":x.retriable,"result":x.result}
