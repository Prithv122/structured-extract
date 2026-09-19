The table below shows all the built-in general-purpose data types. The alternatives listed in the aliases column can be used to refer to these types as well, however, note that the aliases are not part of the SQL standard and hence might not be accepted by other database engines.

| Name                       | Aliases                            | Description                                                                                                |
| :------------------------- | :--------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| `BIGINT`                   | `INT8`, `LONG`                     | Signed eight-byte integer                                                                                  |
| `BIT`                      | `BITSTRING`                        | String of 1s and 0s                                                                                        |
| `BLOB`                     | `BYTEA`, `BINARY`, `VARBINARY`     | Variable-length binary data                                                                                |
| `BIGNUM`                   |                                    | Variable-length integer                                                                                    |
| `BOOLEAN`                  | `BOOL`, `LOGICAL`                  | Logical Boolean (`true` / `false`)                                                                         |
| `DATE`                     |                                    | Calendar date (year, month, day)                                                                           |
| `DECIMAL(prec, scale)`     | `NUMERIC(prec, scale)`             | Fixed-precision number with the given width (precision) and scale, defaults to `prec = 18` and `scale = 3` |
| `DOUBLE`                   | `FLOAT8`                           | Double precision floating-point number (8 bytes)                                                           |
| `FLOAT`                    | `FLOAT4`, `REAL`                   | Single precision floating-point number (4 bytes)                                                           |
| `HUGEINT`                  |                                    | Signed sixteen-byte integer                                                                                |
| `INTEGER`                  | `INT4`, `INT`, `SIGNED`            | Signed four-byte integer                                                                                   |
| `INTERVAL`                 |                                    | Date / time delta                                                                                          |
| `JSON`                     |                                    | JSON object (via the [`json` extension]({% link docs/current/data/json/overview.md %}))                    |
| `SMALLINT`                 | `INT2`, `SHORT`                    | Signed two-byte integer                                                                                    |
| `TIME`                     |                                    | Time of day (no time zone)                                                                                 |
| `TIMESTAMP WITH TIME ZONE` | `TIMESTAMPTZ`                      | Combination of time and date that uses the current time zone                                               |
| `TIMESTAMP`                | `DATETIME`                         | Combination of time and date                                                                               |
| `TINYINT`                  | `INT1`                             | Signed one-byte integer                                                                                    |
| `UBIGINT`                  |                                    | Unsigned eight-byte integer                                                                                |
| `UHUGEINT`                 |                                    | Unsigned sixteen-byte integer                                                                              |
| `UINTEGER`                 |                                    | Unsigned four-byte integer                                                                                 |
| `USMALLINT`                |                                    | Unsigned two-byte integer                                                                                  |
| `UTINYINT`                 |                                    | Unsigned one-byte integer                                                                                  |
| `UUID`                     |                                    | [UUID data type]({% link docs/current/sql/data_types/numeric.md %}#universally-unique-identifiers-uuids)   |
| `VARCHAR`                  | `CHAR`, `BPCHAR`, `TEXT`, `STRING` | Variable-length character string                                                                           |

Implicit and explicit typecasting is possible between numerous types, see the [Typecasting]({% link docs/current/sql/data_types/typecasting.md %}) page for details.
