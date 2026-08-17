# Manifest Domain Design

Status: Phase 2 foundation implemented for review.

## Authority and storage

The central Factory-KM MSSQL database is the authoritative Manifest state
store. Tables and migrations belong to the dedicated `manifest` schema and are
owned by Factory-KM. Authentication tables remain under `auth`.

`D:\KM\Vault` remains authoritative for content and artifacts. A PageIndex
workspace is derived and rebuildable. Manifest records may store safe relative
locators, but absolute Windows paths are never identities.

## Identity

Each persisted artifact version has:

- `StableDocumentId`
- `DocumentVersionId`
- Optional external `SourceResourceId` and source version
- Content SHA-256

Supported external logical references include ResourceId prefixes `MAN_`,
`DWG_`, `SUP_`, `QUO_`, `PUR_`, `DOC_`, and `EPT_`, plus `CNT_`,
`KepwarePath`, and `TaskId`. They are metadata only and have no foreign keys to
OpcTagManager databases.

## Artifact and lifecycle state

Artifact roles are original source, detail Markdown, summary Markdown,
extracted Markdown, and curated Markdown. Training states preserve current
`NotTrained`, `Trained`, and `TrainingError` semantics, with `NotApplicable`
for artifacts outside training.

Lifecycle is `active` or `retired`. Historical versions remain stored. Normal
PageIndex eligibility requires an active, trained Markdown role.

PageIndex states are `not_indexed`, `pending`, `indexed`, `failed`, and
`retired`. Index transitions use attempt count, last error, workspace document
mapping, timestamps, SQL transactions, and SQL Server rowversion optimistic
concurrency.

Concurrent discovery takes SQL Server update/range locks inside the discovery
transaction before applying uniqueness checks. Worker state transitions require
the last observed rowversion and fail rather than overwrite a newer state.

## Idempotency

Database constraints protect StableDocumentId, DocumentVersionId, one logical
SourceResourceId mapping, content discovery by stable document/role/SHA, and
source-version discovery by stable document/role/source version/SHA. Discovery
returns an existing record for the same logical source version and SHA.

A changed SHA or source version is representable by a new DocumentVersionId.

## PageIndex discovery contract

The repository exposes active trained Markdown, selected PageIndex states, and
records missing workspace mappings. It supports mark-attempt, mark-indexed,
mark-failed, and mark-retired transitions. It does not generate workspaces or
call Azure.

## Future audit boundary

Manifest mutation methods retain stable target identity, timestamps, state,
and concurrency information so a later Audit Domain can record:

- `ManifestCreated`
- `VersionDiscovered`
- `TrainingStateChanged`
- `IndexPending`
- `Indexed`
- `IndexFailed`
- `Retired`
- `Recovered`

This foundation does not implement production audit persistence.
