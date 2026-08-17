# Factory-KM Next Steps

## Current milestone

**Current Git milestone:** Architecture foundation completed.

**Product phase:** Phase 2 — PageIndex.

**Immediate implementation prerequisite:** Manifest Domain.

Required ordering: Manifest Domain, PageIndex generation/discovery,
incremental sync/state transitions, recovery/resume/locking, Dictionary, then
LLM Wiki.

**Authentication phase:** Completed for now. No further authentication work
until production cutover.

Node.js remains the production authentication authority, and FastAPI auth-v2
remains disabled by default.

**Temporary development focus:** Engineering Document Extraction Foundation.
Manifest Domain and Manifest-driven PageIndex discovery are complete. Further
PageIndex workspace generation, Dictionary, and LLM Wiki work are paused, not
removed or replaced. This slice starts after successful Training Markdown and
adds evidence-bearing Quotation/Manual drafts, read-only OpcTagManager lookup,
and human review without canonical writes.

## Prioritized roadmap

### Priority 1 — Manifest Domain

- Define manifest identity, record lifecycle, document/version references, and
  event semantics.
- Establish boundaries needed by Vault changes and PageIndex synchronization.
- Persist Manifest state in the central Factory-KM MSSQL database under the
  dedicated `manifest` schema. Use transactions, rowversion concurrency, and
  database uniqueness constraints. Do not use SQLite, filesystem JSON, or
  plant-specific Manifest databases.

### Priority 2 — PageIndex Generator and Lifecycle

- Generate/discover eligible active trained Markdown from Manifest records.
- Add stable document mapping and incremental sync/state transitions.
- Add recovery, resume, locking, and operational visibility afterward.
- Preserve Folder Search as the safe fallback.

### Priority 3 — Audit Domain

- Define audit event identity, actor attribution, action, target, outcome, and
  factory context.
- Keep audit records distinct from authentication sessions and Vault-specific
  transport models.
- Defer persistence selection until the domain contract is stable.

### Priority 4 — Vault API

- Implement authorization-aware Vault orchestration behind the existing
  contracts.
- Add filesystem, recycle-bin, manifest-event, and audit integrations in
  controlled phases.
- Register routes only when authorization and recovery behavior are verified.

### Priority 5 — Vault Web Management

- Build management workflows only after the Vault API contract stabilizes.
- Preserve production login behavior and avoid introducing user management in
  this phase.

### Priority 6 — Dictionary

- Define Dictionary ownership, storage, lifecycle, and factory boundaries.
- Implement runtime and training integration only after those contracts are
  approved.

### Priority 7 — LLM Wiki

- Define Wiki inputs and lifecycle after Manifest, Audit, Vault, PageIndex, and
  Dictionary foundations are stable.
- Do not implement Wiki generation before upstream identity and synchronization
  behavior is available.

## Deferred work

- Production authentication cutover and shared-session decisions.
- User-management UI, add-user CLI, Node user seeding, and multi-plant user
  assignments.
- Factory Context loading, selection, persistence, and runtime integration.
- Knowledge Graph and Conversation Memory.
- Confirmed OpcTagManager create/update/link operations, extraction draft
  persistence/orchestration, shared Identity/Auth, and KMVaultManager migration.
