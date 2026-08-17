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

OpcTagManager candidates do not currently guarantee a dedicated canonical
version/rowversion field. Factory-KM preserves any version metadata returned,
but future controlled execution requires an authoritative canonical revision
contract. A read-only Kepware Tag search API is also not currently available;
KepwarePath can only be entered explicitly for future intent preparation.
