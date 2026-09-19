With the `preserve_identifier_case` [configuration option]({% link docs/current/configuration/overview.md %}#configuration-reference) set to `false`, all identifiers are turned into lowercase:

```sql
SET preserve_identifier_case = false;
CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi;
SELECT CosineOfPi FROM tbl;
```

| cosineofpi |
|-----------:|
| -1.0       |
