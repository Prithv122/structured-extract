As with regular DuckDB, if you use `SET custom_extension_repository = 'https://some.url.com'`, subsequent loads will be attempted at `https://some.url.com/duckdb-wasm/$duckdb_version_hash/$duckdb_platform/$name.duckdb_extension.wasm`.

Note that `GET` requests for the extensions must be [CORS enabled](https://www.w3.org/wiki/CORS_Enabled) for a browser to allow the connection; see [Troubleshoot]({% link docs/current/clients/wasm/troubleshoot.md %}#extension-fails-to-load-from-a-custom-repository) if a load fails.
