Temporary tables are session scoped, meaning that only the specific connection that created them can access them and once the connection to DuckDB is closed they will be automatically dropped (similar to PostgreSQL, for example).

They can be created using the `CREATE TEMP TABLE` or the `CREATE TEMPORARY TABLE` statement (see diagram below) and are part of the `temp.main` schema. While discouraged, their names can overlap with the names of the regular database tables. In these cases, temporary tables take priority in name resolution and full qualification is required to refer to a regular table e.g., `memory.main.t1`.

Temporary tables reside in memory rather than on disk even when connecting to a persistent DuckDB, but if the `temp_directory` [configuration]({% link docs/current/configuration/overview.md %}) is set, data will be spilled to disk if memory becomes constrained.

Create a temporary table from a CSV file (automatically detecting column names and types):

```sql
CREATE TEMP TABLE t1 AS
    SELECT *
    FROM read_csv('path/file.csv');
```

Allow temporary tables to off-load excess memory to disk:

```sql
SET temp_directory = '/path/to/directory/';
```
