In order to persist secrets between DuckDB database instances, we can now use the `CREATE PERSISTENT SECRET` command, e.g.:

```sql
CREATE PERSISTENT SECRET my_persistent_secret (
    TYPE s3,
    KEY_ID 'my_secret_key',
    SECRET 'my_secret_value'
);
```

By default, this will write the secret (unencrypted) to the `~/.duckdb/stored_secrets` directory. To change the secrets directory, issue:

```sql
SET secret_directory = 'path/to/my_secrets_dir';
```

The `secret_directory` setting applies to the current DuckDB instance and is not persisted across DuckDB instances. If you use a custom secrets directory, set `secret_directory` again when starting a new DuckDB instance before creating or using persistent secrets from that directory.

Note that setting the value of the `home_directory` configuration option has no effect on the location of the secrets.
