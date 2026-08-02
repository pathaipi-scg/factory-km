# FastAPI Authentication V2 Manual Test

The active Node.js login remains on port `3006`. These checks target only the
isolated FastAPI service on `127.0.0.1:8000`.

## 1. Prepare an isolated database

Set configuration in the shell used to start FastAPI:

```powershell
$env:AUTH_FASTAPI_ENABLED = "true"
$env:AUTH_SQLITE_PATH = "D:\AI\factory-km\data\auth-v2-test.sqlite3"
```

Explicitly bootstrap the first admin once. Replace the example password before
running this command:

```powershell
@'
from backend.config.auth import AuthSettings
from backend.services.auth.bootstrap import bootstrap_first_admin

bootstrap_first_admin(
    AuthSettings.from_environment(),
    username="admin",
    password="replace-with-a-strong-test-password",
    display_name="Administrator",
)
'@ | .venv\Scripts\python.exe -
```

## 2. Start FastAPI

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## 3. Check isolated status

```powershell
curl.exe http://127.0.0.1:8000/api/auth-v2/status
```

Expected fields are `enabled`, `database_reachable`, and
`schema_initialized`; no database path or credentials are returned.

## 4. Login and retain the cookie

```powershell
curl.exe -i -c auth-v2.cookies -H "Content-Type: application/json" -d '{"username":"admin","password":"replace-with-a-strong-test-password"}' http://127.0.0.1:8000/api/auth-v2/login
```

Confirm the response contains `success`, `role`, and `name`, and that
`km_session` has `HttpOnly`, `Path=/`, `SameSite=Lax`, and `Max-Age=86400`.

## 5. Resolve the current user

```powershell
curl.exe -b auth-v2.cookies http://127.0.0.1:8000/api/auth-v2/me
```

## 6. Test viewer login

```powershell
curl.exe -i -c viewer-v2.cookies -X POST http://127.0.0.1:8000/api/auth-v2/login/viewer
curl.exe -b viewer-v2.cookies http://127.0.0.1:8000/api/auth-v2/me
```

## 7. Logout and verify revocation

```powershell
curl.exe -i -b auth-v2.cookies -X POST http://127.0.0.1:8000/api/auth-v2/logout
curl.exe -i -b auth-v2.cookies http://127.0.0.1:8000/api/auth-v2/me
```

The final request should return HTTP `401` with `{"loggedIn":false}`.

## 8. Verify isolation

The following FastAPI paths must remain absent:

```text
/api/login
/api/login/viewer
/api/logout
/api/me
```

Unset `AUTH_FASTAPI_ENABLED` or set it to `false`, restart FastAPI, and confirm
`/api/auth-v2/status` returns `404` because the router is not registered.
