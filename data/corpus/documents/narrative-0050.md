PostgreSQL is case-insensitive. The way PostgreSQL achieves case insensitivity is by lowercasing unquoted identifiers within SQL, whereas quoting preserves case, e.g., the following command creates a table named `mytable` but tries to query for `MyTaBLe` because quotes preserve the case.

```sql
CREATE TABLE MyTaBLe (x INTEGER);
SELECT * FROM "MyTaBLe";
```

```console
ERROR:  relation "MyTaBLe" does not exist
```

PostgreSQL does not only treat quoted identifiers as case-sensitive; it treats all identifiers as case-sensitive, e.g., this also does not work:

```sql
CREATE TABLE "PreservedCase" (x INTEGER);
SELECT * FROM PreservedCase;
```

```console
ERROR:  relation "preservedcase" does not exist
```

Therefore, case-insensitivity in PostgreSQL only works if you never use quoted identifiers with different cases.

For DuckDB, this behavior was problematic when interfacing with other tools (e.g., Parquet, Pandas) that are case-sensitive by default – since all identifiers would be lowercased all the time.
Therefore, DuckDB achieves case insensitivity by making identifiers fully case insensitive throughout the system but [_preserving their case_]({% link docs/current/sql/dialect/keywords_and_identifiers.md %}#rules-for-case-sensitivity).

In DuckDB, the scripts above complete successfully:

```sql
CREATE TABLE MyTaBLe (x INTEGER);
SELECT * FROM "MyTaBLe";
CREATE TABLE "PreservedCase" (x INTEGER);
SELECT * FROM PreservedCase;
SELECT tbl FROM duckdb_tables();
```

<div class="monospace_table"></div>

| tbl    |
| ------------- |
| MyTaBLe       |
| PreservedCase |

PostgreSQL's behavior of lowercasing identifiers is accessible using the [`preserve_identifier_case` option]({% link docs/current/configuration/overview.md %}#local-configuration-options):

```sql
SET preserve_identifier_case = false;
CREATE TABLE MyTaBLe (x INTEGER);
SELECT tbl FROM duckdb_tables();
```

<div class="monospace_table"></div>

| tbl |
| ---------- |
| mytable    |

However, the case insensitive matching in the system for identifiers cannot be turned off.
