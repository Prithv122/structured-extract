To avoid having to continuously fetch schema data from PostgreSQL, DuckDB keeps schema information – such as the names of tables, their columns, etc. – cached. If changes are made to the schema through a different connection to the PostgreSQL instance, such as new columns being added to a table, the cached schema information might be outdated. In this case, the function `pg_clear_cache` can be executed to clear the internal caches.

```sql
CALL pg_clear_cache();
```

In version 1.5.5 a support for automatic detection of schema changes was added using a "staleness query"
(contributed by Brandon Freeman in [duckdb/duckdb-postgres#514](https://github.com/duckdb/duckdb-postgres/pull/514)):

 - when `pg_staleness_query_enabled` option (`BOOLEAN`, default: `FALSE`) is enabled, on every catalog access a query is run that
   checks Postgres' `pg_class.xmin` column value in every table and reloads the cache automatically, if a change is detected

 - for Postgres-wire-compatible databases a custom "staleness query" can be set using `pg_staleness_query` option.
