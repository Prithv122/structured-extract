Create a table with two integer columns (`i` and `j`):

```sql
CREATE TABLE t1 (i INTEGER, j INTEGER);
```

Create a table with a primary key:

```sql
CREATE TABLE t1 (id INTEGER PRIMARY KEY, j VARCHAR);
```

Create a table with a composite primary key:

```sql
CREATE TABLE t1 (id INTEGER, j VARCHAR, PRIMARY KEY (id, j));
```

Create a table with various different types, constraints and default values:

```sql
CREATE TABLE t1 (
    i INTEGER NOT NULL DEFAULT 0,
    decimalnr DOUBLE CHECK (decimalnr < 10),
    date DATE UNIQUE,
    time TIMESTAMP
);
```

Create table with `CREATE TABLE ... AS SELECT` (CTAS):

```sql
CREATE TABLE t1 AS
    SELECT 42 AS i, 84 AS j;
```

Create a table from a CSV file (automatically detecting column names and types):

```sql
CREATE TABLE t1 AS
    SELECT *
    FROM read_csv('path/file.csv');
```

We can use the `FROM`-first syntax to omit `SELECT *`:

```sql
CREATE TABLE t1 AS
    FROM read_csv('path/file.csv');
```

Copy the schema of `t2` to `t1`:

```sql
CREATE TABLE t1 AS
    FROM t2
    LIMIT 0;
```

Note that only the column names and types are copied to `t1`, other pieces of information (indexes, constraints, default values, etc.) are not copied.
