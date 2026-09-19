By default, extensions are installed under the user's home directory:

```sql
~/.duckdb/extensions/⟨duckdb_version⟩/⟨platform_name⟩/
```

For stable DuckDB releases, the `⟨duckdb_version⟩`{:.language-sql .highlight} will be equal to the version tag of that release. For nightly DuckDB builds, it will be equal
to the short git hash of the build. So for example, the extensions for DuckDB version v0.10.3 on macOS ARM64 (Apple Silicon) are installed to `~/.duckdb/extensions/v0.10.3/osx_arm64/`.
An example installation path for a nightly DuckDB build could be `~/.duckdb/extensions/fc2e4b26a6/linux_amd64`.

To change the default location where DuckDB stores its extensions, use the `extension_directory` configuration option:

```sql
SET extension_directory = '/path/to/your/extension/directory';
```

To specify multiple directories for loading extensions (e.g., for package managers or air-gapped environments), use the `extension_directories` option:

```sql
SET extension_directories = ['/usr/lib/duckdb/extensions', '/opt/duckdb/extensions'];
```

Note that setting the value of the `home_directory` configuration option has no effect on the location of the extensions.
