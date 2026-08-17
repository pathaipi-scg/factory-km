# Engineering Document Extraction Design

Status: Foundation slice approved for implementation on 2026-08-17.

## Ownership

Factory-KM owns document upload, existing Office/PDF-to-Markdown Training,
engineering-document extraction, and human review drafts. OpcTagManager owns
canonical `KepwarePath`, `SUP_`, `CNT_`, `EPT_`, `MAN_`, `DWG_`, `QUO_`, and
`DOC_` identities and engineering relationships. KMVaultManager and shared
Identity/Auth remain deferred.

## Hook point

Extraction runs only from a successfully trained KM package after
`TrainingService.train_one()` has written both detail and summary Markdown.
It does not create another conversion, OCR, or vision pipeline and does not
depend on PageIndex, Dictionary, LLM Wiki, or a live Manifest migration.

## Domain boundary

The extraction result is a persistence-neutral review draft containing:

- path-independent source identity, source content SHA-256, extractor version,
  and prompt/schema version;
- classification as quotation, manual, drawing, datasheet, catalog,
  general_document, or unknown, with confidence and evidence;
- quotation or manual draft values where applicable;
- Supplier, Supplier-owned Contact, and physical Equipment/Part drafts;
- all plausible read-only OpcTagManager candidates;
- provisional human decisions clearly separated from extracted and canonical
  candidate state.

Important extracted values carry confidence and source evidence identifying
the detail/summary Markdown artifact and page/slide/section. Absolute Windows
paths are never domain identities or integration payloads.

## AI contract

The extraction service reuses the existing provider-agnostic LLM contract and
Azure OpenAI provider. The model must return one JSON object conforming to the
versioned extraction schema. Invalid JSON, unsupported types, out-of-range
confidence, or structurally invalid output fails safely. AI output is always a
draft and never performs canonical mutation.

## Canonical lookup

Factory-KM calls OpcTagManager over HTTP using a configured
`OPC_TAG_MANAGER_BASE_URL`. Only these read endpoints are allowed:

- `GET /api/suppliers/candidates`
- `GET /api/contacts/candidates`
- `GET /api/equipment-parts/candidates`
- `GET /api/suppliers/{resource_id}/equipment-parts`
- `GET /api/resource-relationships/{source_resource_id}`

Responses must contain logical IDs and canonical metadata, not physical Vault
paths. Failures, timeouts, malformed responses, and unexpected physical-path
fields fail safely. The client has no write methods.

## Review state

The smallest review UI displays classification, evidence, quotation/manual
fields, issuer Supplier versus customer, Contacts, line concepts, and canonical
candidates. A reviewer may provisionally select an existing candidate in the
draft. Disabled future-create controls communicate that canonical creation is
not implemented. No selection invokes an OpcTagManager write API.

## Idempotency direction

`source_document_id + source_content_sha256 + extractor_version +
schema_version` distinguishes a repeat extraction from a new source revision.
This slice does not introduce production orchestration or persistence.

## Engineering review persistence

The authoritative workflow store is the central Factory-KM MSSQL database in
the dedicated `engineering` schema. It is separate from `auth` and `manifest`.
Factory-KM owns idempotent schema migrations, but migrations are not applied
live during foundation development.

`engineering.ExtractionRuns` identifies an immutable extraction snapshot by
logical source identity, source SHA-256, extractor version, and schema version.
`EXR_` identity and a unique idempotency key distinguish reruns from source or
extractor revisions. The snapshot preserves extraction evidence and the exact
candidate response seen at review time.

`engineering.Reviews` owns mutable review state and decisions under SQL Server
rowversion optimistic concurrency. `REV_` reviews transition through draft,
in_review, confirmed, or cancelled. Raw extraction is never rewritten.

`engineering.Commands` stores deterministic `CMD_` confirmed-operation intents
with unique idempotency keys. Confirmation creates READY commands only. No
executor or canonical OpcTagManager mutation endpoint exists in this phase.

OpcTagManager Phase 4.10 now supplies `canonical_revision`, generic canonical
state reads, bounded OPC Tag search, controlled document canonicalization, and
the existing additive relationship APIs.

## Controlled canonical execution - Phase 1

A confirmed review remains distinct from remote execution. Only persisted
READY commands are eligible for the serial lifecycle `claim -> preflight ->
mutation -> succeeded/conflict/failed`. Execution is disabled by default with
`ENGINEERING_CANONICAL_WRITE_ENABLED=false`; dry-run remains available and
never claims commands or calls a mutation API. OpcTagManager retains its
independent `KM_RESOURCE_WRITE_ENABLED` server gate.

The allowlist contains existing-identity validation, source-document
canonicalization, and additive Resource/Supplier, Resource/EPT, and EPT/Tag
relationships. Supplier, Contact, and EPT create/update proposals and all
unlink/delete/retire/merge operations are blocked for a future master-data
phase. There is no arbitrary HTTP command facility.

Every existing canonical selection is re-read immediately before mutation.
The reviewed `canonical_revision` must equal current state; Contact selections
use the owning Supplier revision. Exact KepwarePath search must return the
same active path. Stale, missing, inactive, unsafe, or ambiguous state becomes
CONFLICT and is never silently refreshed.

Original bytes are obtained through a `SourceDocumentProvider` using the
logical `KM_...` source identity. The Training adapter performs the trusted
Vault resolution internally and verifies the extraction SHA-256. Commands do
not contain bytes or absolute paths. Document canonicalization supports
quotation, manual, drawing, and general_document through
`POST /api/integration/resources`; similarity requiring human choice becomes
CONFLICT.

Command claiming uses a lease, attempt counter, and atomic repository method.
SQL Server uses transaction-safe update locks; expired leases are recoverable.
Structured result/failure metadata and audit events are persisted. Execution
is serial and dependency ordered. Completed remote operations are never
compensated destructively; retry skips SUCCEEDED commands and resumes from the
safe point. Production enablement still requires separate operational and
service-authorization approval; shared Identity/Auth remains deferred.
