By default, DuckDB sorts `ASC` and `NULLS LAST`, i.e., the values are sorted in ascending order and `NULL` values are placed last.
For the default `ASC` direction this matches PostgreSQL. Note, however, that DuckDB keeps `NULLS LAST` even for `DESC` ordering, whereas PostgreSQL places `NULL`s first on `DESC` (it treats `NULL` as the largest value). To match PostgreSQL in both directions, set `default_null_order = 'NULLS_LAST_ON_ASC_FIRST_ON_DESC'`.
The default sort order can be changed with the following configuration options.

Use the `default_null_order` option to change the default `NULL` sorting order to either `NULLS_FIRST`, `NULLS_LAST`, `NULLS_FIRST_ON_ASC_LAST_ON_DESC` or `NULLS_LAST_ON_ASC_FIRST_ON_DESC`:

```sql
SET default_null_order = 'NULLS_FIRST';
```

Use the `default_order` option to change the direction of the default sorting order to either `DESC` or `ASC`:

```sql
SET default_order = 'DESC';
```
