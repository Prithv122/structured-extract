The DuckDB logging mechanism can be enabled or disabled using a special function, `enable_logging`. Logs are stored in a special view
named `duckdb_logs`, which can be queried like any standard table.

Example:

```sql
CALL enable_logging();
-- Run some queries...
SELECT * FROM duckdb_logs;
```

To disable logging, run

```sql
CALL disable_logging();
```

To clear the current log, run

```sql
CALL truncate_duckdb_logs();
```
