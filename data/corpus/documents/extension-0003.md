Idle connection in a pool are available for any caller thread, be it a DuckDB internal worker thread or a new client thread. In some cases it may be beneficial to ensure, that subsequent queries from the same thread are run on the same connection as the first query.
To support this the `pg_pool_enable_thread_local_cache` configuration option can be used - it makes an idle connection to be returned to a thread-local (and thread-private) cache instead of the main cache shared between all threads.

> Warning 
> Thread-local connection are not checked and not cleaned up by the reaper thread. Thread-local cache should be used with caution as cached connections, while not available to other threads, are still take the place in the pool, so can cause a "pool startvation".
