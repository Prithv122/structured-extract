Set the memory limit of the system to 10 GB.

```sql
SET memory_limit = '10GB';
```

Configure the system to use 1 thread.

```sql
SET threads TO 1;
```

Turn logging on and set the logging level to `debug`.
For additional details on logging levels, see [Log Level]({% link docs/current/operations_manual/logging/overview.md %}#log-level).

```sql
SET enable_logging = true;
SET logging_level = 'debug';
```

Write a single log message with the `debug` level and a `connection` scope:

```sql
SELECT write_log('A new client has connected.', level := 'debug', scope := 'connection');
```

Write a single log message with a `debug` level and a `connection` scope and a custom `log_type`:

```sql
SELECT write_log(
        'A new duck has connected to the lake.', 
        level := 'debug', 
        scope := 'connection', 
        log_type := 'duckdb.docs.example.quack'
    );
```

Check logs with the `DEBUG` log level:

```sql
SELECT * FROM duckdb_logs WHERE log_level = 'DEBUG';
```

Check logs with the `QueryLog` type:

```sql
SELECT * FROM duckdb_logs WHERE type = 'QueryLog';
```

Check current logging settings:

```sql
SELECT * FROM duckdb_settings() WHERE name LIKE '%logging%';
```

Enable printing of a progress bar during long-running queries:

```sql
SET enable_progress_bar = true;
```

Set the default null order to `NULLS LAST`:

```sql
SET default_null_order = 'nulls_last';
```

Return the current value of a specific setting:

```sql
SELECT current_setting('threads') AS threads;
```

| threads |
| ------: |
|      10 |

Query a specific setting:

```sql
SELECT *
FROM duckdb_settings()
WHERE name = 'threads';
```

| name    | value | description                                     | input_type | scope  |
| ------- | ----- | ----------------------------------------------- | ---------- | ------ |
| threads | 1     | The number of total threads used by the system. | BIGINT     | GLOBAL |

Show a list of all available settings:

```sql
SELECT *
FROM duckdb_settings();
```

Reset the memory limit of the system back to the default:

```sql
RESET memory_limit;
```
