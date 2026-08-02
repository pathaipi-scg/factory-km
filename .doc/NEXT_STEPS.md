# Factory-KM Next Steps

## Current milestone

**Current Git milestone:** Architecture foundation completed.

**Authentication phase:** Completed for now. No further authentication work
until production cutover.

Node.js remains the production authentication authority, and FastAPI auth-v2
remains disabled by default.

## Prioritized roadmap

### Priority 1 — Manifest Domain

- Define manifest identity, record lifecycle, document/version references, and
  event semantics.
- Establish boundaries needed by Vault changes and PageIndex synchronization.
- Do not implement persistence or generation until the domain contract is
  approved.

### Priority 2 — Audit Domain

- Define audit event identity, actor attribution, action, target, outcome, and
  factory context.
- Keep audit records distinct from authentication sessions and Vault-specific
  transport models.
- Defer persistence selection until the domain contract is stable.

### Priority 3 — Vault API

- Implement authorization-aware Vault orchestration behind the existing
  contracts.
- Add filesystem, recycle-bin, manifest-event, and audit integrations in
  controlled phases.
- Register routes only when authorization and recovery behavior are verified.

### Priority 4 — Vault Web Management

- Build management workflows only after the Vault API contract stabilizes.
- Preserve production login behavior and avoid introducing user management in
  this phase.

### Priority 5 — PageIndex Generator

- Generate local PageIndex workspace data from eligible document versions.
- Add stable document mapping, synchronization, resume, recovery, and
  operational visibility.
- Preserve Folder Search as the safe fallback.

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
