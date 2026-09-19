Larger-than-memory workloads are supported by spilling to disk.
With the default configuration, DuckDB creates the `⟨database_file_name⟩.tmp`{:.language-sql .highlight} temporary directory (in persistent mode) or the `.tmp`{:.language-sql .highlight} directory (in in-memory mode). This directory can be changed using the [`temp_directory` configuration option]({% link docs/current/configuration/pragmas.md %}#temp-directory-for-spilling-data-to-disk), e.g.:

```sql
SET temp_directory = '/path/to/temp_dir.tmp/';
```
