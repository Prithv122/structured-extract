To set DuckDB options when the database instance starts, build a `Config` and open the connection with `Connection::open_with_flags()` (or `Connection::open_in_memory_with_flags()`). `Config` uses a builder style: each method consumes the config and returns it, and each returns a `Result` because DuckDB validates the option:

```rust
use duckdb::{Config, Connection, Result};

let config = Config::default()
    .max_memory("4GB")?
    .threads(4)?;
let conn = Connection::open_with_flags("my_database.duckdb", config)?;
```

`Config` exposes typed methods for the most common options, including `access_mode()`, `max_memory()`, `threads()`, `default_order()`, `default_null_order()`, `enable_external_access()`, `enable_object_cache()`, `custom_user_agent()`, and `allow_unsigned_extensions()`. Any other DuckDB setting can be supplied by name with `with()`:

```rust
let config = Config::default()
    .with("temp_directory", "/path/to/temp/dir/")?
    .with("preserve_insertion_order", "false")?;
```

The full list of settings is on the [Configuration page]({% link docs/current/configuration/overview.md %}). Many of them can also be changed after connecting with a [`SET` statement]({% link docs/current/sql/statements/set.md %}) or the equivalent [`PRAGMA`]({% link docs/current/configuration/pragmas.md %}).
