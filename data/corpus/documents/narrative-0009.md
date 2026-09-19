DuckDB offers the following security levels for extensions.

| Usable extensions | Description | Configuration |
|-----|---|---|
| `core` | Extensions can only be loaded if signed from a `core` key. | `SET allow_community_extensions = false` |
| `core` and `community` | Extensions can only be loaded if signed from a `core` or `community` key. | This is the default security level. |
| Any extension including unsigned | Any extensions can be loaded. | `SET allow_unsigned_extensions = true` |

Security-related configuration settings [lock themselves]({% link docs/current/operations_manual/securing_duckdb/overview.md %}#locking-configurations), i.e., it is only possible to restrict capabilities in the current process.

For example, attempting the following configuration changes will result in an error:

```sql
SET allow_community_extensions = false;
SET allow_community_extensions = true;
```

```console
Invalid Input Error:
Cannot upgrade allow_community_extensions setting while database is running
```
