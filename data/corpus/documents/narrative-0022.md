DuckDB can automatically load [core extensions]({% link docs/current/core_extensions/overview.md %}) when certain SQL statements require them. To maintain full control over which extensions are loaded, you can disable autoloading:

```sql
SET autoload_known_extensions = false;
SET autoinstall_known_extensions = false;
```
