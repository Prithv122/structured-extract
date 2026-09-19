> Warning Only load unsigned extensions from sources you trust.
> Avoid loading unsigned extensions over HTTP.
> Consult the [Securing DuckDB page]({% link docs/current/operations_manual/securing_duckdb/securing_extensions.md %}) for guidelines on how to set up DuckDB in a secure manner.

If you wish to load your own extensions or extensions from third-parties you will need to enable the `allow_unsigned_extensions` flag.
To load unsigned extensions using the [CLI client]({% link docs/current/clients/cli/overview.md %}), pass the `-unsigned` flag to it on startup:

```batch
duckdb -unsigned
```

Now any extension can be loaded, signed or not:

```sql
LOAD './some/local/ext.duckdb_extension';
```

For client APIs, the `allow_unsigned_extensions` database configuration options needs to be set, see the respective [Client API docs]({% link docs/current/clients/overview.md %}).
For example, for the Python client, see the [Loading and Installing Extensions section in the Python API documentation]({% link docs/current/clients/python/overview.md %}#loading-and-installing-extensions).
