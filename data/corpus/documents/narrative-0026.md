DuckDB-Wasm fetches each extension over the network when it is loaded. If you serve extensions from a [custom repository]({% link docs/current/clients/wasm/deploying_duckdb_wasm.md %}#duckdb-extensions) with `SET custom_extension_repository = '⟨https://some.url.com⟩'`, the `GET` requests for the extension files must be [CORS enabled](https://www.w3.org/wiki/CORS_Enabled) for the browser to allow the connection, exactly as for remote data files above.

Extensions remain signed regardless of where they are served, so copying an extension to a different location keeps its signature valid.
