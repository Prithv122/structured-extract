DuckDB extensions for DuckDB-Wasm, similar for the native cases, are served signed at the default extension endpoint: `https://extensions.duckdb.org`.
If you are deploying duckdb-wasm you can consider mirroring relevant extensions at a different endpoint, possibly allowing for air-tight deployments on internal networks.

```sql
SET custom_extension_repository = '⟨https://some.endpoint.org/path/to/repository⟩';
```

Changes the default extension repository from the public `https://extensions.duckdb.org` to the one specified. Note that extensions are still signed, so the best path is downloading and serving the extensions with a similar structure to the original repository. See the additional notes on [Creating a Custom Repository]({% link docs/current/extensions/extension_distribution.md %}#creating-a-custom-repository).

Community extensions are served at <https://community-extensions.duckdb.org>, and they are signed with a different key, so they can be disabled with a one way SQL statement such as:

```sql
SET allow_community_extensions = false;
```

This will allow loading **only** of core duckdb extensions. Note that the failure is at `LOAD` time, not at `INSTALL` time.

Please review the [Extension Distribution page]({% link docs/current/extensions/extension_distribution.md %}) for general information about extensions.
