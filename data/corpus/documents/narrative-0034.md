Converting a TIMESTAMP_TZ value to a string depends on a timezone offset.
By default, this is set to the offset for the local timezone when the Node
process is started.

To change it, set the `timezoneOffsetInMinutes`
property of `DuckDBTimestampTZValue`:

```ts
DuckDBTimestampTZValue.timezoneOffsetInMinutes = -8 * 60;
const pst = DuckDBTimestampTZValue.Epoch.toString();
// 1969-12-31 16:00:00-08

DuckDBTimestampTZValue.timezoneOffsetInMinutes = +1 * 60;
const cet = DuckDBTimestampTZValue.Epoch.toString();
// 1970-01-01 01:00:00+01
```

Note that the timezone offset used for this string
conversion is distinct from the `TimeZone` setting of DuckDB.

The following sets this offset to match the `TimeZone` setting of DuckDB:

```ts
const reader = await connection.runAndReadAll(
  `select (timezone(current_timestamp) / 60)::int`
);
DuckDBTimestampTZValue.timezoneOffsetInMinutes =
  reader.getColumns()[0][0];
```
