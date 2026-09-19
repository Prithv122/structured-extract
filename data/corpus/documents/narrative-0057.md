The `union_by_name` option can be used to unify the schema of files that have different or missing columns. For files that do not have certain columns, `NULL` values are filled in.

```sql
SELECT * FROM read_csv('flights*.csv', union_by_name = true);
```

To load data into _an existing table_ where the table has more columns than the CSV file, you can use the [`INSERT INTO ... BY NAME` clause]({% link docs/current/sql/statements/insert.md %}#insert-into--by-name):

```sql
INSERT INTO tbl BY NAME
    SELECT * FROM read_csv('input.csv');
```
