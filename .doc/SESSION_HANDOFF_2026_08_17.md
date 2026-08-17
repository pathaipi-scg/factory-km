# Session Handoff — 2026-08-17

Read this file first when resuming development. It records the verified state
at the end of the 2026-08-17 session and does not depend on chat history.

## 1. Verified Git state at stop time

### Factory-KM — `D:\AI\factory-km`

- Branch: `main`
- HEAD: `82d2ded2139556a03f49150c3d017362c70f6245`
- HEAD subject: `Add engineering review persistence and confirmed command foundation`
- `origin/main` was at the same commit when inspected.
- The Manifest/extraction foundation and engineering review/READY-command
  foundation are committed through `d803fcb` and `82d2ded`.
- Engineering Controlled Canonical Execution Phase 1 is implemented only in
  the working tree. It is not committed or pushed and awaits review.

Tracked modified files before this handoff file was added:

```text
.doc/ARCHITECTURE_DECISIONS.md
.doc/DECISION_LOG.md
.doc/ENGINEERING_DOCUMENT_EXTRACTION_DESIGN.md
.doc/NEXT_STEPS.md
.doc/PROJECT_STATUS.md
.doc/SESSION_STATUS.md
.env.example
assets/js/ask_AI_multi.js
backend/db/engineering_mssql_migrations.py
backend/domain/engineering_review.py
backend/repositories/engineering_review_memory.py
backend/repositories/engineering_review_mssql.py
backend/repositories/engineering_review_protocols.py
backend/routers/engineering.py
backend/services/opc_tag_manager_client.py
backend/services/training_service.py
tests/test_engineering_mssql_migration.py
tests/test_engineering_review.py
tests/test_engineering_review_api.py
tests/test_opc_tag_manager_client.py
```

Untracked executor-related files before this handoff file was added:

```text
backend/config/engineering_execution.py
backend/services/engineering_execution_service.py
backend/services/source_document_provider.py
tests/test_engineering_execution.py
```

This handoff file is an additional untracked documentation file until a later
explicit commit.

### OpcTagManager — `D:\AI\OpcTagManager`

- Branch: `main`
- HEAD: `5dfd093139a4e0cf4eb2acba03f3c55b597fed14`
- HEAD subject: `Add Phase 4.10 canonical integration contracts`
- HEAD matched `origin/main` when inspected.
- Working tree: clean.
- Phases 4.8, 4.9, and 4.10 are committed. Phase 4.10 was approved.
- Git required `--git-dir/--work-tree` read-only inspection because normal Git
  reported repository ownership safety; Git configuration was not changed.

### KMVaultManager — `D:\AI\KMVaultManager`

- Branch/symbolic HEAD: `master`
- HEAD commit: none; this is an unborn repository.
- Every foundation artifact remains untracked: `.env.example`, `.gitignore`,
  `README.md`, `docs/`, `src/`, and `tests/`.
- The foundation is therefore not committed or pushed.

## 2. Multi-project ownership

Factory-KM owns document upload, Office/PDF-to-Markdown Training, engineering
document AI extraction, human review, `EXR_` extraction runs, `REV_` reviews,
`CMD_` commands, Chat, Task, Operational Memory, and Manifest/PageIndex
architecture.

OpcTagManager owns canonical `KepwarePath`, Supplier `SUP_`, Supplier-contained
Contact `CNT_`, Equipment/Part `EPT_`, canonical document Resources, Tag
Knowledge, engineering relationships, and the canonical revision contract.

KMVaultManager is a separate future Vault storage/version/integrity foundation.
It is not integrated into production Factory-KM or OpcTagManager workflows.

Shared User Authentication / IdentityService is deferred. Do not work on it.

## 3. Factory-KM completed and approved foundations

### Manifest Domain Foundation

Implemented and committed in the central Factory-KM architecture. Factory-KM
owns the `manifest.*` MSSQL migrations. The domain uses stable/path-independent
document and version identities, lifecycle state, SHA/version discovery,
transactions, uniqueness/idempotency constraints, and rowversion optimistic
concurrency. No live Manifest migration has been applied.

### Manifest-driven PageIndex discovery

Implemented and committed as a read/planning boundary using Manifest contracts.
It does not generate a PageIndex workspace and does not make Azure calls.

### Paused roadmap work

- PageIndex workspace generation: paused / not started.
- Dictionary: paused.
- LLM Wiki: paused.

Do not replace or skip these roadmap items, but do not resume them in the next
session because the active focus is controlled engineering execution.

### Engineering Document Extraction Foundation

Implemented and committed. It reuses the existing Training pipeline:

```text
uploaded Office/PDF
  -> Training / conversion / vision
  -> detail Markdown + summary Markdown
  -> engineering extraction draft
```

Supported classifications are `quotation`, `manual`, `drawing`, `datasheet`,
`catalog`, `general_document`, and `unknown`. Drafts preserve confidence and
source evidence. Quotation extraction separates issuer/Supplier from customer
or buyer, captures Supplier Contact drafts, and distinguishes physical
Equipment/Part quotation lines from service/freight/installation/other lines.
Manual extraction includes Equipment/Part concepts. OpcTagManager candidate
lookup is read-only and preserves ambiguous Supplier, Contact, and EPT matches;
it never auto-selects or mutates canonical master data.

## 4. Engineering review and READY-command foundation

The committed foundation is:

```text
Document
  -> Extraction
  -> EXR_<uuid>
  -> immutable extraction snapshot
  -> REV_<uuid>
  -> human decisions
  -> Confirm
  -> deterministic CMD_<uuid>
  -> READY
```

The authoritative planned persistence is the central Factory-KM MSSQL database
under the dedicated `engineering.*` schema, separate from `auth` and `manifest`.
Migration code exists, but no live engineering migration has been applied.

`ExtractionRuns` preserve immutable source identity, SHA-256, extractor/schema
versions, evidence, and exact candidate snapshots. Review decisions never
rewrite raw extraction. Reviews use `ROWVERSION` optimistic concurrency and
support draft, in-review, confirmed, and cancelled states. Commands use stable
`CMD_` identity and unique idempotency keys. The original committed command
states were ready, executing, succeeded, failed, conflict, and cancelled; the
current uncommitted Phase 1 migration/domain also adds blocked and execution
lease/result fields.

Critical distinction:

> Confirmed Review != Canonical Changes Executed

## 5. Approved OpcTagManager state

Phase 4.8 — Canonical Engineering Relationship Foundation: approved and
committed.

Phase 4.9 — Engineering Relationship Management UI and Candidate APIs:
approved and committed.

Phase 4.10 — Canonical Integration Contracts: approved and committed at
`5dfd093`.

The normalized revision is:

```text
v<active_version>:<active_version_sha256>
```

Important APIs include:

```text
GET  /api/canonical/{canonical_id}
GET  /api/opc-tags/search
POST /api/integration/resources
GET  /api/suppliers/candidates
GET  /api/contacts/candidates
GET  /api/equipment-parts/candidates
GET  /api/suppliers/{resource_id}/equipment-parts
GET  /api/resource-relationships/{source_resource_id}
POST /api/resource-relationships/link
POST /api/resource-relationships/unlink
POST /api/tag-resources/link
```

The approved graph is:

```text
KepwarePath -> EPT_ -> SUP_
EPT_ -> MAN_
EPT_ -> DWG_
EPT_ -> QUO_
EPT_ -> DOC_
SUP_ -> QUO_
KepwarePath -> ResourceId   (existing direct link remains supported)
```

## 6. Critical work-in-progress: Controlled Canonical Execution Phase 1

The workspace safety review initially paused mutation-capable code generation.
The user then explicitly approved adding mutation-capable executor code behind
the disabled-by-default gate. That approval was for code implementation only,
not live execution.

Contrary to the earlier planning checkpoint, the execution service now does
exist. The current Factory-KM working tree contains a substantially complete
Phase 1 implementation awaiting review:

- `backend/config/engineering_execution.py`: false-by-default execution gate
  and bounded lease duration.
- `backend/services/engineering_execution_service.py`: allowlisted dry-run,
  whole-review guard, serial execution, repeated per-command preflight,
  canonical revision/Tag/SHA checks, claiming, structured results, conflict
  classification, partial-failure stop, and retry behavior.
- `backend/services/source_document_provider.py`: protocol, trusted Training
  adapter, and in-memory test provider.
- `backend/services/opc_tag_manager_client.py`: narrowly scoped Phase 4.10
  reads and mutation methods using fixed configured-origin endpoints.
- `backend/services/training_service.py`: safe logical `KM_` source-content
  resolution with trained-state, filename, and Vault-containment checks.
- Domain/repository/MSSQL migration changes for leases, results, failure codes,
  retriable classification, audit references, and `blocked` status.
- Factory-KM dry-run, execution, and status APIs.
- Minimal Engineering Review UI showing Canonical Execution, blocked
  master-data commands, Dry Run, and conditionally enabled Execute.
- `tests/test_engineering_execution.py` plus updates to client/API/migration and
  existing review tests.
- Architecture, decision, status, and next-step documentation updates.

The implementation is not merely documentation/config scaffolding. A real
execution service and mutation-capable client methods have been added in the
working tree, but the gate remains false and no live composition was exercised.
The phase has not been committed, pushed, live-migrated, or live-validated.

Known implementation detail: Factory-KM previously accepted dotted test Tag
paths, while the approved OpcTagManager contract returns slash-separated paths.
The uncommitted domain/test change now validates slash-separated paths such as
`LP2/MIX/Tag` and rejects Windows backslashes/invalid hierarchies.

## 7. Executor authorization and dual safety gates

Mutation-capable executor code is explicitly authorized. Live mutation is not.

Factory-KM default:

```text
ENGINEERING_CANONICAL_WRITE_ENABLED=false
```

OpcTagManager independent server gate:

```text
KM_RESOURCE_WRITE_ENABLED=false
```

Both gates must deliberately permit writes before any real canonical mutation.
Do not modify the real `.env` or enable either side without later explicit
operational approval.

## 8. Phase 1 allowlist and blocked operations

Allowed low-risk additive/idempotent operations:

- Validate `UseExistingSupplier`.
- Validate `UseExistingContact` using the owning Supplier revision.
- Validate `UseExistingEquipmentPart`.
- Canonicalize reviewed documents: Manual -> `MAN_`, Drawing -> `DWG_`,
  Quotation -> `QUO_`, General Document -> `DOC_`.
- Add Resource/Supplier relationship in the direction supported by the
  OpcTagManager graph.
- Add Resource/EquipmentPart relationship.
- Add EquipmentPart/KepwarePath relationship through existing Tag/Resource link.
- Add direct Resource/Tag link only through the existing safe endpoint.

Explicitly blocked:

- Create/update Supplier.
- Create/update Contact.
- Create/update EquipmentPart.
- Identity merge or automatic candidate merge.
- Unlink, delete, retire, replace, destructive overwrite, or compensation.

## 9. Required execution behavior

- Dry-run performs no claims or mutation calls.
- Real execution repeats preflight immediately before each mutation.
- Reviewed canonical revisions must equal current revisions.
- `CNT_` staleness is protected through `supplier_canonical_revision`.
- EPT/Tag operations require an exact active KepwarePath; never substitute.
- Trusted source bytes must match the reviewed source SHA-256.
- Exact duplicate Resource creation is idempotent.
- `similar_resource_found` requires human decision and becomes CONFLICT.
- Atomic claim changes eligible work to EXECUTING with lease and incremented
  attempt count; active leases reject a second worker and expired leases recover.
- Retry is operator-triggered, not a background spin loop.
- Structured results distinguish conflict, blocked, validation, transport, and
  retriable failures.
- Execution is serial and dependency ordered.
- Retry skips SUCCEEDED commands.
- Successful remote operations are retained after later failure.
- Never automatically roll back through unlink/delete.
- Record audit-compatible dry-run, claim, preflight, success, conflict, failure,
  and stop events.

## 10. Source document content rule

Command JSON must not contain raw bytes and must not use an absolute Windows
path as identity. The intended and now implemented abstraction is:

```text
logical source document identity
  -> SourceDocumentProvider
  -> trusted Factory-KM source bytes
```

The current Training adapter resolves a logical `KM_...` identity internally,
checks containment, and returns bytes plus SHA. Tests use in-memory content. If
future source kinds cannot be resolved this way, report the gap instead of
adding an unsafe filesystem-path workaround.

## 11. APIs and migration code currently in the working tree

Factory-KM endpoints added but not live-validated:

```text
POST /api/engineering/reviews/{review_id}/execution/dry-run
POST /api/engineering/reviews/{review_id}/execution
GET  /api/engineering/reviews/{review_id}/execution
```

Engineering migration version 2 code adds command lease ID/expiry, structured
result JSON, failure code, retriable flag, audit command/failure references,
lease index, JSON constraint, and blocked status. It has not been applied live.

## 12. Test status

Latest verified scoped run after executor implementation:

```text
30 tests passed
```

It covered execution, review, review API, OpcTagManager client, MSSQL migration,
and Training behavior. JavaScript syntax and `git diff --check` passed at that
checkpoint.

Latest practical environment-independent repository regression:

```text
147 tests passed, 1 skipped
```

Full discovery observed 158 tests total: 156 passed, one skipped, and two
unrelated environment-dependent failures. The configured KM root/local fixture
environment made the expected local Vault unavailable and also defeated the
Vault configuration test's unset/default assumption:

```text
test_pageindex_local_adapter.LocalPageIndexAdapterTests.test_folder_search_regression_hash_is_unchanged
test_vault_config.VaultSettingsTests.test_unset_uses_backward_compatible_default
```

Do not classify these two failures as executor failures. Do not access the live
Vault merely to make them pass.

## 13. Production status — not done or approved

- Live `engineering.*` migration: not applied/approved.
- Live Manifest migration: not applied/approved.
- Live Factory-KM -> OpcTagManager mutation: not performed/approved.
- Production executor enablement: disabled/not approved.
- Production cross-project service authorization: deferred.
- Shared Identity/Auth service: deferred.
- Supplier/Contact/EPT master-data executor: blocked/deferred.
- PageIndex workspace generation: paused/not started.
- Dictionary: paused.
- LLM Wiki: paused.
- KMVaultManager workflow migration: not implemented.

## 14. Review concerns for the next session

Before calling Phase 1 complete, inspect the entire uncommitted Factory-KM diff
and re-run the scoped tests. Pay particular attention to MSSQL claim/completion
lease ownership, audit event persistence, response sanitization, dependency
ordering, existing canonical Resource revision expectations, and API/UI status
serialization. Do not assume the current working tree is committed merely
because the implementation is substantial.

The exact remaining gap before any controlled live validation is operational,
not permission to write code: central MSSQL access and approved migration,
service reachability/authorization, deliberate dual-gate enablement in a
controlled environment, selection of one bounded reviewed document/relationship,
and retained clean dry-run evidence. Each requires later explicit approval.

## 15. NEXT SESSION

1. Read this handoff first.
2. Inspect Factory-KM Git diff/status; preserve the uncommitted Phase 1 work.
3. Do not resume PageIndex, Dictionary, or LLM Wiki.
4. Resume Engineering Controlled Canonical Execution Phase 1 review/completion.
5. Use the existing explicit authorization for gated mutation-capable executor
   code; the execution service already exists, so audit and finish it rather
   than starting over.
6. Keep `ENGINEERING_CANONICAL_WRITE_ENABLED=false`.
7. Use mocks, TEMP roots, and in-memory fixtures only.
8. Do not apply live migrations or perform cross-project writes.
9. Stop for review when the executor foundation is genuinely complete.

No commit or push was performed for this handoff.
