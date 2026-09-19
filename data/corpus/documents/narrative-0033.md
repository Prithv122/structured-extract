To turn off the join order optimizer, set the following [`PRAGMA`s]({% link docs/current/configuration/pragmas.md %}):

```sql
SET disabled_optimizers = 'join_order,build_side_probe_side';
```

This disables both the join order optimizer and left/right swapping for joins.
This way, DuckDB builds a left-deep join tree following the order of `JOIN` clauses.

```sql
SELECT ...
FROM ...
JOIN ...  -- this join is performed first
JOIN ...; -- this join is performed second
```

Once the query in question has been executed, turn back the optimizers with the following command:

```sql
SET disabled_optimizers = '';
```
