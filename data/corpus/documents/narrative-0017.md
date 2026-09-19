> Deprecated DuckDB 1.5.0 deprecated the use of recursive `UNION`s for
> `USING KEY` CTEs in favor of recursive `UNION ALL`s.
> 
> The recursive `UNION`s imply that not all rows that are produced in one
> iteration are passed to the next, as would be the case for regular recursive
> CTEs. Since the opposite is true, i.e., all rows are passed from one iteration
> to the next, going forward DuckDB's `USING KEY` CTEs will require recursive
> `UNION ALL`s instead.
>
> DuckDB 1.5.0 also introduces a new setting to configure the `USING KEY` syntax.
>
> ```sql
> SET deprecated_using_key_syntax = 'DEFAULT';
> SET deprecated_using_key_syntax = 'UNION_AS_UNION_ALL';
> ```
>
> Currently, `DEFAULT` enables both syntax styles, i.e., allows both recursive
> `UNION`s and recursive `UNION ALL`s in `USING KEY` CTEs.
>
> DuckDB 1.5.0 will be the last release supporting the `UNION` syntax without
> explicitly enabling it.
>
> DuckDB 2.0.0 disables the `UNION` syntax by default.
>
> DuckDB 2.1.0 removes the `deprecated_using_key_syntax` flag and fully
> deprecates the `UNION` syntax.

`USING KEY` alters the behavior of a regular recursive CTE.

In each iteration, a regular recursive CTE appends result rows to the union table, which ultimately defines the overall result of the CTE. In contrast, a CTE with `USING KEY` has the ability to update rows that have been placed in the union table in an earlier iteration: if the current iteration produces a row with key `k`, it replaces a row with the same key `k` in the union table (like a dictionary). If no such row exists in the union table yet, the new row is appended to the union table as usual.

This allows a CTE to exercise fine-grained control over the union table contents. Avoiding the append-only behavior can lead to significantly smaller union table sizes. This helps query runtime, memory consumption, and makes it feasible to access the union table while the iteration is still ongoing. In a CTE `WITH RECURSIVE T(...) USING KEY ...`, table `T` denotes the rows added by the last iteration (as is usual for recursive CTEs), while table `recurring.T` denotes the [union table built so far](#accessing-the-union-table-with-recurring). References to `recurring.T` allow for the elegant and idiomatic translation of rather complex algorithms into readable SQL code.
