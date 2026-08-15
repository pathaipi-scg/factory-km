# Factory-KM Project Status

Last updated: 2026-08-02

## Product vision

The informational long-term product direction, from Knowledge Retrieval
through a Closed Learning Loop, is described in
[Factory AI Vision](FACTORY_AI_VISION.md). It does not change the current
implementation status, next steps, or roadmap.

## Completed today

- Microsoft SQL Server authentication persistence using the shared
  `SQL_SERVER`, `SQL_DB`, `SQL_USER`, and `SQL_PASS` configuration.
- The `auth` schema and authentication tables were created successfully in
  database `[factory-km]`.
- `bootstrap_first_admin` compatibility with the MSSQL repositories was
  verified. It creates the `admin` role, `admin` identity, and automatic
  `viewer` identity.
- Core Domain phase 1: stable document and folder identity, audit actors,
  responsibility-only ownership, documents, and document versions.
- Core Domain phase 2: Plant, Department, Process, and Machine reference data.
- Factory Context domain models for stable factory identity and plant-specific
  runtime configuration boundaries.

## Current production status

- Node.js on port `3006` remains the production authentication authority.
- The frontend continues to use the Node login, viewer login, logout, and
  current-user endpoints.
- FastAPI `/api/auth-v2` remains experimental and disabled by default through
  `AUTH_FASTAPI_ENABLED=false`.
- Node and FastAPI sessions are not shared.
- `[factory-km]` is the central authentication database.
- Only the `admin` and `viewer` MSSQL authentication identities are in scope.
- `KM_SEARCH_MODE` defaults to `folder`.
- Folder Search remains the safe production search path and PageIndex fallback.

## Current architecture status

- The architecture foundation milestone is complete.
- Authentication models, services, MSSQL repositories, session handling,
  Argon2id password hashing, bootstrap, and disabled compatibility endpoints
  are complete for the current phase.
- Shared Core Domain models define stable document identity, document
  aggregates and versions, folder identity, audit actors, ownership, and
  factory reference data.
- Factory Context models describe the database, Vault, PageIndex workspace,
  Dictionary, Wiki, and chat namespace belonging to one plant. Context
  loading and runtime selection are not implemented.
- Vault Management currently provides contracts only. Its router is
  unregistered and filesystem mutations are not implemented.
- PageIndex search-policy integration and a read-only local workspace client
  exist. Workspace generation, synchronization, and multi-document resolution
  are not implemented.
- SQLite authentication code remains inactive compatibility and regression-test
  infrastructure; active FastAPI auth composition uses MSSQL.

## Outstanding work

1. Define the Manifest Domain.
2. Define the Audit Domain and later select audit persistence.
3. Implement the authorized Vault API and concrete filesystem behavior.
4. Build Vault Web Management after the API and authorization boundaries are
   stable.
5. Implement PageIndex workspace generation, identity mapping,
   synchronization, recovery, and operational monitoring.
6. Implement Dictionary domain and runtime behavior.
7. Implement LLM Wiki only after its upstream document and indexing contracts
   are stable.
8. Add Factory Context loading, selection, persistence, and runtime composition
   in a later phase.
9. Defer authentication work until production cutover planning resumes.

## Risks

- Node and FastAPI authentication are separate authorities with incompatible
  sessions; accidental route cutover would break active login behavior.
- FastAPI auth has not been cut over or proven under production traffic.
- SQLite authentication code remains in the tree and could be composed by
  mistake outside the established MSSQL runtime boundary.
- Vault mutations must not ship before authorization, audit, manifest, and
  recovery behavior are defined.
- PageIndex currently depends on pre-generated local workspace data and cannot
  generate or synchronize that data.
- Factory Context is a domain model only; treating it as runtime configuration
  before a loader and selection policy exist would create inconsistent plant
  boundaries.
- Dictionary and LLM Wiki remain undefined downstream capabilities.

## Known design decisions

- Authentication is shared centrally through database `[factory-km]`; plant
  runtime data is isolated through Factory Context.
- Node.js remains the production authentication authority until an explicit,
  tested cutover.
- FastAPI auth-v2 remains disabled by default and isolated under its temporary
  prefix.
- Authentication work is complete for now. No further authentication changes
  are planned until production cutover.
- Factory-KM currently uses only `admin` and `viewer`; user-management UI,
  add-user tooling, Node user seeding, and multi-plant assignments are deferred.
- Stable document and factory identities do not use filesystem paths, plant
  codes, or PageIndex document IDs as identity.
- Ownership represents responsibility, not authorization.
- Plant, Department, Process, and Machine are reference data, not
  authorization scopes.
- Detail Markdown and summary Markdown remain separate Document aggregates.
- Each plant owns its Vault, PageIndex workspace, Dictionary, LLM Wiki, and
  chat namespace; authentication remains shared.
- Folder Search remains the safe default and fallback.

Authentication production cutover remains unfinished even though the current
authentication implementation phase is complete.
