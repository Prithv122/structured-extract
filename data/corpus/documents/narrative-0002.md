You can use the [`memory_limit` configuration option]({% link docs/current/configuration/pragmas.md %}) to limit the memory use of DuckDB, e.g.:

```sql
SET memory_limit = '2GB';
```

Note that this limit is only applied to the memory DuckDB uses and it does not affect the memory use of other R libraries.
Therefore, the total memory used by the R process may be higher than the configured `memory_limit`.
