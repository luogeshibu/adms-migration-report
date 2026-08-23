# Future database integration

Current Excel/CSV inputs are treated as database-query exports. SQL integration should be added through source adapters rather than directly inside the UI.

Recommended future layout:

- `sql/profiles/<source>/queries/*.sql` - version-controlled SELECT templates.
- database connection profiles - server/port/service/database/user metadata only.
- passwords/secrets - Windows Credential Manager or another approved secret store, never plaintext project JSON.
- adapter layer - Oracle/PostgreSQL/SQL Server implementations return the same row dictionaries currently returned by file adapters.

This keeps Comparison, SQLite audit storage and Excel report generation independent from the upstream database vendor.
