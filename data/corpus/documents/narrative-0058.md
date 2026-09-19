> Installation To use the DuckDB Rust client, visit the [Rust installation page]({% link install/index.html %}?environment=rust).
>
> The latest stable version of the DuckDB Rust client is {% if site.current_duckdb_rust_version != "" %}{{ site.current_duckdb_rust_version }}{% else %}{{ site.lts_duckdb_rust_version }}{% endif %}.

The DuckDB Rust client, [`duckdb-rs`](https://github.com/duckdb/duckdb-rs), is an ergonomic wrapper over the [DuckDB C API](https://github.com/duckdb/duckdb/blob/main/src/include/duckdb.h) that exposes an interface modeled on [rusqlite](https://github.com/rusqlite/rusqlite). It supports type-safe queries, bulk loading with the Appender, [Apache Arrow](https://arrow.apache.org/) interchange, user-defined functions, and building DuckDB extensions in Rust. This page focuses on installation. The other pages in this section cover connecting and each feature in detail.
