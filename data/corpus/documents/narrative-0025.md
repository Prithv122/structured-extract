The `TIMESTAMPTZ` type can be binned into calendar and clock bins using a suitable extension.
The built-in [ICU extension]({% link docs/current/core_extensions/icu.md %}) implements all the binning and arithmetic functions using the
[International Components for Unicode](https://icu.unicode.org) time zone and calendar functions.

To set the time zone to use, first load the ICU extension. The ICU extension comes pre-bundled with several DuckDB clients (including Python, R, JDBC and ODBC), so this step can be skipped in those cases. In other cases you might first need to install and load the ICU extension.

```sql
INSTALL icu;
LOAD icu;
```

Next, use the `SET TimeZone` command:

```sql
SET TimeZone = 'America/Los_Angeles';
```

Time binning operations for `TIMESTAMPTZ` will then be implemented using the given time zone.

A list of available time zones can be pulled from the `pg_timezone_names()` table function:

```sql
SELECT
    name,
    abbrev,
    utc_offset
FROM pg_timezone_names()
ORDER BY
    name;
```

You can also find a reference table of [available time zones]({% link docs/current/sql/data_types/timezones.md %}).
