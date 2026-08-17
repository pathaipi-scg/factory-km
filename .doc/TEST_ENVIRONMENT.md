# Factory-KM Test Environment Notes

Last reviewed: 2026-08-17

- The project `.venv` does not currently contain pytest.
- The available alternate test environment does not contain `argon2`, so the
  complete authentication suite cannot be collected there.
- Existing Folder Search/Vault tests can load deployment `.env` values during
  test execution; two previously observed tests therefore depend on local
  `KM_ROOT`/fixture availability rather than being fully isolated.
- Manifest tests use `unittest`, mocked SQL Server connections, and pure domain
  fixtures. They do not require Vault, Azure, Office COM, or a live database.

These are environment/test-isolation notes, not authorization to change
production configuration or persistence architecture.
