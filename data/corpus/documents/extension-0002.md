The `postgres` extension supports running a background thread (so called "reaper thread") that periodically scans idle connections in the pool and closes the ones of them that exceed `idle_timeout_millis` or `max_lifetime_millis` values.

Separate thread is run for each connections pool, it can be enabled/disabled using `pg_pool_enable_reaper_thread` configuraton option.

When the reaper thread is not running, `idle_timeout_millis` or `max_lifetime_millis` values of the connections still can be checked, but they are only checked when a connection is taken from the pool or returned to the pool.
