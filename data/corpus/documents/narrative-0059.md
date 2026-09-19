For [`CREATE TABLE` statements]({% link docs/current/sql/statements/create_table.md %}), DuckDB attempts to resolve type names in the schema where a table is created. For example:

```sql
CREATE SCHEMA myschema;
CREATE TYPE myschema.mytype AS ENUM ('as', 'df');
CREATE TABLE myschema.mytable (v mytype);
```

PostgreSQL returns an error on the last statement:

```console
ERROR:  type "mytype" does not exist
LINE 1: CREATE TABLE myschema.mytable (v mytype);
```

DuckDB runs the statement and creates the table successfully, confirmed by the following query:

```sql
DESCRIBE myschema.mytable;
```

<div class="monospace_table"></div>

| column_name | column_type      | null | key  | default | extra |
| ----------- | ---------------- | ---- | ---- | ------- | ----- |
| v           | ENUM('as', 'df') | YES  | NULL | NULL    | NULL  |
