The local HTTP server fetches the files for the UI from a remote HTTP
server so they can be kept up-to-date.

The default URL for the remote server is <https://ui.duckdb.org>.

An alternate remote URL can be configured with a SQL command like:

```sql
SET ui_remote_url = 'https://ui.duckdb.org';
```

The environment variable `ui_remote_port` can also be used.

This setting is available mainly for testing purposes.

Be sure you trust any URL you configure, as the application can access
the data you load into DuckDB.

Because of this risk, the setting is only respected
if `allow_unsigned_extensions` is enabled.
