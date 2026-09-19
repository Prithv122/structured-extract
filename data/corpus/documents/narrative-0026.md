The `storage_compatibility_version` [configuration option]({% link docs/current/configuration/overview.md %}#configuration-reference) can also be used to specify the storage version to use. It can be specified in various ways.

In the Python client, you have to specify it when connecting to a new database:

```python
duckdb.connect("file.db", config={'storage_compatibility_version': 'latest'})
