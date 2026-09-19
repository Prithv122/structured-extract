The `duckdb_optimizers()` function provides metadata about the optimization rules (e.g., `expression_rewriter`, `filter_pushdown`) available in the DuckDB instance.
These can be selectively turned off using [`PRAGMA disabled_optimizers`]({% link docs/current/configuration/pragmas.md %}#selectively-disabling-optimizers).

| Column | Description | Type |
|:-|:---|:-|
| `name` | The name of the optimization rule. | `VARCHAR` |
