# Authentication Contract and Migration Plan

This module is an isolated design skeleton. The FastAPI auth router is not
registered, and Node.js remains the only active authentication authority.

## Current Node.js contract

### `POST /api/login`

Request JSON:

```json
{"username": "factory", "password": "..."}
```

Success: HTTP 200 and:

```json
{"success": true, "role": "factory", "name": "..."}
```

Invalid credentials: HTTP 401 and:

```json
{"success": false, "error": "..."}
```

### `POST /api/login/viewer`

No request body is required. Success is HTTP 200:

```json
{"success": true, "role": "viewer", "name": "..."}
```

### `POST /api/logout`

No request body is required. Success is HTTP 200:

```json
{"success": true}
```

### `GET /api/me`

Authenticated success is HTTP 200:

```json
{
  "loggedIn": true,
  "username": "factory",
  "role": "factory",
  "name": "..."
}
```

Unauthenticated response is HTTP 401:

```json
{"loggedIn": false}
```

### Session cookie

- Name: `km_session`
- Value: 48-character hexadecimal token generated from 24 random bytes
- Login properties: `HttpOnly; Path=/; SameSite=Lax; Max-Age=86400`
- Logout clears it with: `HttpOnly; Path=/; Max-Age=0`
- `Secure` is not currently set.
- Sessions are stored only in the Node.js process and disappear on restart.

### Viewer and write behavior

- `viewer` may enter without a password, read, and ask questions.
- Node write endpoints call `requireWriteSession` and return HTTP 403 for an
  unauthenticated user or `viewer`.
- The frontend calls `/api/me`; when `role === "viewer"`, it hides elements
  marked `write-only` and replaces the logout control with a viewer badge.
- `/?mode=viewer` creates the same viewer session while serving the app shell.

## New module boundaries

- `backend.models.auth`: identities, roles, groups, memberships, resolved users,
  and sessions.
- `backend.repositories.auth`: persistence-neutral lookup and session protocols.
- `backend.services.auth`: credential, session, and current-user service contracts.
- `backend.dependencies.auth`: FastAPI current-user, role, permission, and scope
  dependency contracts.
- `backend.routers.auth`: unregistered compatibility-route skeleton.

No credential hashing policy or persistent implementation is selected yet.

## Staged migration

1. Select persistent storage and credential hashing; implement repositories
   behind the existing protocols.
2. Implement authentication, session, and current-user services. Store only a
   digest of each opaque cookie token.
3. Add contract tests proving FastAPI responses and `km_session` cookie behavior
   match Node exactly, including viewer login and logout.
4. Introduce a temporary shared session store readable by both Node and FastAPI.
   Do not cut over while sessions remain process-local to Node.
5. Register the FastAPI auth router behind a disabled migration flag and verify
   the existing frontend without changes.
6. Migrate read-only current-user resolution first, then login/viewer/logout.
7. Apply permission and scope dependencies to future Vault Management routes.
8. Migrate existing write guards only after role/permission equivalence is
   verified. Remove Node auth last.

## Compatibility risks

- Node and FastAPI cannot validate each other's in-memory sessions.
- Changing the cookie name, path, SameSite policy, lifetime, or response fields
  would break the existing frontend.
- The current single `role` string must remain available while richer roles and
  groups are introduced.
- Viewer is both a session type and a role in the current implementation.
- UI hiding is not authorization; every write route still requires server-side
  permission checks.
- Adding `Secure` requires HTTPS and coordinated deployment.
- Existing sessions disappear on Node restart; persistent sessions change that
  operational behavior and require an explicit revocation/expiry policy.
