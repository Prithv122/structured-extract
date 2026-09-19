Prior to version 0.10.0, DuckDB would automatically allow any type to be implicitly cast to `VARCHAR` during function binding. As a result it was possible to e.g., compute the substring of an integer without using an explicit cast. For version v0.10.0 and later an explicit cast is needed instead. To revert to the old behavior that performs implicit casting, set the `old_implicit_casting` variable to `true`:

```sql
SET old_implicit_casting = true;
```
