In in-process mode, DuckDB has two configurable options for concurrency:

1. **Read-write mode:** one process can both read and write to the database.
2. **Read-only mode:** multiple processes can read from the database, but no processes can write ([`access_mode = 'READ_ONLY'`]({% link docs/current/configuration/overview.md %}#configuration-reference)).

When using read-write mode, DuckDB supports multiple writer threads using a combination of [MVCC (Multi-Version Concurrency Control)](https://en.wikipedia.org/wiki/Multiversion_concurrency_control) and optimistic concurrency control (see [Concurrency within a Single Process](#concurrency-model-within-a-single-process)), but all within that single writer process. The reason for this concurrency model is to allow for the caching of data in RAM for faster analytical queries, rather than going back and forth to disk during each query. It also allows the caching of function pointers, the database catalog, and other items so that subsequent queries on the same connection are faster.
