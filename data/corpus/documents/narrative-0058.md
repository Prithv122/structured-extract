Conceptually, a `STRUCT` column contains an ordered list of columns called “entries”. The entries are referenced by name using strings. This document refers to those entry names as keys. Each row in the `STRUCT` column must have the same keys. The names of the struct entries are part of the *schema*. Each row in a `STRUCT` column must have the same layout. The names of the struct entries are case-insensitive.

`STRUCT`s are typically used to nest multiple columns into a single column, and the nested column can be of any type, including other `STRUCT`s and `LIST`s.

`STRUCT`s are similar to PostgreSQL's `ROW` type. The key difference is that DuckDB `STRUCT`s require the same keys in each row of a `STRUCT` column. This allows DuckDB to provide significantly improved performance by fully utilizing its vectorized execution engine, and also enforces type consistency for improved correctness. DuckDB includes a `row` function as a special way to produce a `STRUCT`, but does not have a `ROW` data type. See an example below and the [`STRUCT` functions documentation]({% link docs/current/sql/functions/struct.md %}) for details.

See the [data types overview]({% link docs/current/sql/data_types/overview.md %}) for a comparison between nested data types.
