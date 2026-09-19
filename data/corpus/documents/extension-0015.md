| Name | Description | Default |
|------|-------------|---------|
| `mysql_bit1_as_boolean` | Whether or not to convert `BIT(1)` columns to `BOOLEAN` | `true` |
| `mysql_debug_show_queries` | DEBUG SETTING: print all queries sent to MySQL to stdout | `false` |
| `mysql_enable_filter_pushdown` | Whether or not to use filter pushdown (without predicate analyzer) | `true` |
| `mysql_enable_transactions` | Whether to run `START TRANSACTION` / `COMMIT` / `ROLLBACK` on MySQL connections | `true` |
| `mysql_incomplete_dates_as_nulls` | Whether to return `DATE`s with a zero month or day as `NULL`s | `false` |
| `mysql_pool_acquire_mode` | How to acquire connections from the pool: `force` (always connect, ignoring the pool limit), `wait` (block until one is available), or `try` (fail immediately if none is available) | `force` |
| `mysql_pool_connection_idle_timeout_millis` | Maximum time in milliseconds a connection can sit idle in the cache before being closed | `60000` |
| `mysql_pool_connection_max_lifetime_millis` | Maximum age in milliseconds of a pooled connection since it was first opened; when exceeded, the connection is closed instead of being returned to the cache (`0` disables it) | `0` |
| `mysql_pool_enable_reaper_thread` | Whether to run a dedicated thread that periodically scans the pool and removes expired connections | `true` |
| `mysql_pool_enable_thread_local_cache` | Enable thread-local connection caching for faster same-thread connection reuse | `false` |
| `mysql_pool_size` | Maximum number of connections per MySQL catalog | automatic (based on the CPU count) |
| `mysql_pool_wait_timeout_millis` | Timeout in milliseconds when waiting for a connection from the pool | `30000` |
| `mysql_session_time_zone` | Session time zone to set for newly opened connections to the MySQL server | `''` |
| `mysql_time_as_time` | Whether or not to convert MySQL's `TIME` columns to DuckDB's `TIME` | `false` |
| `mysql_tinyint1_as_boolean` | Whether or not to convert `TINYINT(1)` columns to `BOOLEAN` | `true` |
