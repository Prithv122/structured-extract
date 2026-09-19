The `EXPLAIN` statement supports additional settings that can be used to control the output. The following settings are available:

The default setting. Only shows the physical plan.

```sql
PRAGMA explain_output = 'physical_only';
```

Shows only the optimized plan.

```sql
PRAGMA explain_output = 'optimized_only';
```

Shows both the physical and optimized plans.

```sql
PRAGMA explain_output = 'all';
```
