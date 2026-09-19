Identifiers in DuckDB are always case-insensitive, similarly to PostgreSQL.
However, unlike PostgreSQL (and some other major SQL implementations), DuckDB also treats quoted identifiers as case-insensitive.

**Comparison of identifiers:**
Case-insensitivity is implemented using an ASCII-based comparison:
`col_A` and `col_a` are equal but `col_á` is not equal to them.

```sql
SELECT col_A FROM (SELECT 'x' AS col_a); -- succeeds
SELECT col_á FROM (SELECT 'x' AS col_a); -- fails
```

**Preserving cases:**
While DuckDB treats identifiers in a case-insensitive manner, it preserves the cases of these identifiers.
That is, each character's case (uppercase/lowercase) is maintained as originally specified by the user even if a query uses different cases when referring to the identifier.
For example:

```sql
CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi;
SELECT cosineofpi FROM tbl;
```

| CosineOfPi |
|-----------:|
| -1.0       |

To change this behavior, set the `preserve_identifier_case` [configuration option]({% link docs/current/configuration/overview.md %}#configuration-reference) to `false`.
