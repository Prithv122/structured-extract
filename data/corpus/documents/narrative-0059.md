The function `list_sort` sorts the elements of a list either in ascending or descending order.
In addition, it allows specifying whether `NULL` values should be moved to the beginning or to the end of the list.
It has the same sorting behavior as DuckDB's `ORDER BY` clause.
Therefore, (nested) values compare the same in `list_sort` as in `ORDER BY`.

By default, if no modifiers are provided, DuckDB sorts `ASC NULLS LAST`.
I.e., the values are sorted in ascending order and `NULL` values are placed last.
This is identical to the default sort order of SQLite.
The default sort order can be changed using [`PRAGMA` statements.](../query_syntax/orderby).

`list_sort` leaves it open to the user whether they want to use the default sort order or a custom order.
`list_sort` takes up to two additional optional parameters.
The second parameter provides the sort order and can be either `ASC` or `DESC`.
The third parameter provides the `NULL` order and can be either `NULLS FIRST` or `NULLS LAST`.

This query uses the default sort order and the default `NULL` order.

```sql
SELECT list_sort([1, 3, NULL, 5, NULL, -5]);
```

```sql
[-5, 1, 3, 5, NULL, NULL]
```

This query provides the sort order.
The `NULL` order uses the configurable default value.

```sql
SELECT list_sort([1, 3, NULL, 2], 'ASC');
```

```sql
[1, 2, 3, NULL]
```

This query provides both the sort order and the `NULL` order.

```sql
SELECT list_sort([1, 3, NULL, 2], 'DESC', 'NULLS FIRST');
```

```sql
[NULL, 3, 2, 1]
```

`list_reverse_sort` has an optional second parameter providing the `NULL` sort order.
It can be either `NULLS FIRST` or `NULLS LAST`.

This query uses the default `NULL` sort order.

```sql
SELECT list_sort([1, 3, NULL, 5, NULL, -5]);
```

```sql
[-5, 1, 3, 5, NULL, NULL]
```

This query provides the `NULL` sort order.

```sql
SELECT list_reverse_sort([1, 3, NULL, 2], 'NULLS LAST');
```

```sql
[3, 2, 1, NULL]
```
