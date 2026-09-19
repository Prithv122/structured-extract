To install extensions from the default repository (`core`), run:

```sql
INSTALL httpfs;
```

To explicitly install an extension from the core repository, run:

```sql
INSTALL httpfs FROM core;
-- or
INSTALL httpfs FROM 'http://extensions.duckdb.org';
```

To install an extension from the core nightly repository:

```sql
INSTALL spatial FROM core_nightly;
-- or
INSTALL spatial FROM 'http://nightly-extensions.duckdb.org';
```

To install an extension from a custom repository:

```sql
INSTALL ⟨custom_extension⟩ FROM 'https://my-custom-extension-repository';
```

Alternatively, the `custom_extension_repository` setting can be used to change the default repository used by DuckDB:

```sql
SET custom_extension_repository = 'http://nightly-extensions.duckdb.org';
```

DuckDB contains the following predefined repositories:

| Alias                 | URL                                      | Description                                                                            |
|:----------------------|:-----------------------------------------|:---------------------------------------------------------------------------------------|
| `core`                | `http://extensions.duckdb.org`           | DuckDB core extensions                                                                 |
| `core_nightly`        | `http://nightly-extensions.duckdb.org`   | Nightly builds for `core`                                                              |
| `community`           | `http://community-extensions.duckdb.org` | DuckDB community extensions                                                            |
| `local_build_debug`   | `./build/debug/repository`               | Repository created when building DuckDB from source in debug mode (for development)    |
| `local_build_release` | `./build/release/repository`             | Repository created when building DuckDB from source in release mode (for development)  |
