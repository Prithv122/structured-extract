The collations we have seen so far have all been specified *per expression*. It is also possible to specify a default collator, either on the global database level or on a base table column. The `PRAGMA` `default_collation` can be used to specify the global default collator. This is the collator that will be used if no other one is specified.

```sql
SET default_collation = NOCASE;
SELECT 'hello' = 'HeLlo';
```

```text
true
```

Collations can also be specified per-column when creating a table. When that column is then used in a comparison, the per-column collation is used to perform that comparison.

```sql
CREATE TABLE names (name VARCHAR COLLATE NOACCENT);
INSERT INTO names VALUES ('hännes');
```

```sql
SELECT name
FROM names
WHERE name = 'hannes';
```

```text
hännes
```

Be careful here, however, as different collations cannot be combined. This can be problematic when you want to compare columns that have a different collation specified.

```sql
SELECT name
FROM names
WHERE name = 'hannes' COLLATE NOCASE;
```

```console
ERROR: Cannot combine types with different collation!
```

```sql
CREATE TABLE other_names (name VARCHAR COLLATE NOCASE);
INSERT INTO other_names VALUES ('HÄNNES');
```

```sql
SELECT names.name AS name, other_names.name AS other_name
FROM names, other_names
WHERE names.name = other_names.name;
```

```console
ERROR: Cannot combine types with different collation!
```

We need to manually overwrite the collation:

```sql
SELECT names.name AS name, other_names.name AS other_name
FROM names, other_names
WHERE names.name COLLATE NOACCENT.NOCASE = other_names.name COLLATE NOACCENT.NOCASE;
```

|  name  | other_name |
|--------|------------|
| hännes | HÄNNES     |
