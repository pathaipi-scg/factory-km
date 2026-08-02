# Factory-KM Project Status

Last updated: 2026-08-02

## Completed implementation

- PageIndex search-policy integration with `folder` as the safe default.
- Read-only filesystem PageIndex runtime for one configured, pre-generated
  local workspace document.
- Folder Search fallback for missing, unavailable, invalid, or corrupt
  PageIndex runtime data.
- Authentication domain contracts and migration plan.
- SQLite authentication schema, repositories, and migrations.
- Argon2id password hashing and explicit first-admin bootstrap.
- FastAPI authentication services for credentials, viewer sessions, session
  lifecycle, and current-user resolution.
- Experimental `/api/auth-v2` compatibility endpoints.
- Conditional FastAPI auth-router registration behind
  `AUTH_FASTAPI_ENABLED`.
- Vault Management domain, repository, authorization, orchestration, audit,
  and manifest-event contracts.
- Core Domain phase 1 framework-neutral models for stable document and folder
  identity, audit actors, responsibility-only ownership, documents, and
  document versions.

## Active production behavior

- Node.js on port `3006` remains the production authentication authority.
- The active frontend still calls Node endpoints:
  - `POST /api/login`
  - `POST /api/login/viewer`
  - `POST /api/logout`
  - `GET /api/me`
- FastAPI authentication is experimental and isolated under `/api/auth-v2`.
- `AUTH_FASTAPI_ENABLED` defaults to `false`; when false, the experimental
  router is not registered.
- Node and FastAPI sessions are not shared.
- `KM_SEARCH_MODE` defaults to `folder`.
- PageIndex mode reads pre-generated local `document.json`, `structure.json`,
  and `pages.json` data and falls back to Folder Search on failure.
- Vault Management contains contracts only. Its router is unregistered and no
  filesystem mutation implementation exists.

## Authentication migration remains unfinished

- Manually test `/api/auth-v2` on localhost.
- Bootstrap the first admin and viewer identities in an isolated test SQLite
  database.
- Decide between direct cutover and a temporary compatibility period.
- Decide whether a shared Node/FastAPI session store is required during
  migration.
- Migrate `/api/me` only after compatibility verification.
- Migrate login, viewer login, and logout only after `/api/me` succeeds.
- Apply FastAPI `CurrentUser`, role, permission, and scope enforcement to
  protected APIs.
- Configure `Secure` cookies when HTTPS is deployed.
- Remove Node authentication only after successful cutover and rollback
  validation.

Authentication cutover is not complete. Node authentication must not be
removed or bypassed yet.

## PageIndex remaining work

- Generate PageIndex workspace data from eligible trained Markdown.
- Resolve and map multiple documents.
- Implement manifests and deterministic document identity mapping.
- Implement incremental synchronization, resume, and recovery.
- Add production workspace lifecycle and operational monitoring.

No PageIndex generation, synchronization, manifest, resume, or recovery
implementation currently exists.

## Vault Management remaining work

- Select concrete filesystem and persistence implementations.
- Implement authorization policy evaluation.
- Implement listing, metadata reads, mutations, recycle-bin behavior, audit
  persistence, and manifest-event publishing.
- Register Vault routes only after authentication cutover and authorization
  enforcement are ready.

## Not implemented

- Core Domain models beyond phase 1, including shared Plant, Department,
  Process, Machine, ManifestRecord, and IndexState models.
- Dictionary runtime and training workflow.
- LLM Wiki.
- Knowledge Graph.
- Conversation Memory.
- Multi-factory support.
