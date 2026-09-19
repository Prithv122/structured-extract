The output of [`EXPLAIN`]({% link docs/current/sql/statements/profiling.md %}) can be configured to show only the physical plan.

The default configuration of `EXPLAIN`:

```sql
SET explain_output = 'physical_only';
```

To only show the optimized query plan:

```sql
SET explain_output = 'optimized_only';
```

To show all query plans:

```sql
SET explain_output = 'all';
```
