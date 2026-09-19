The `AT TIME ZONE` syntax is syntactic sugar for the (two argument) `timezone` function listed above:

```sql
SELECT TIMESTAMP '2001-02-16 20:38:40' AT TIME ZONE 'America/Denver' AS ts;
```

```text
2001-02-16 19:38:40-08
```

```sql
SELECT TIMESTAMP WITH TIME ZONE '2001-02-16 20:38:40-05' AT TIME ZONE 'America/Denver' AS ts;
```

```text
2001-02-16 18:38:40
```

Note that numeric timezones are not allowed:

```sql
SELECT TIMESTAMP '2001-02-16 20:38:40-05' AT TIME ZONE '0200' AS ts;
```

```console
Not implemented Error: Unknown TimeZone '0200'
```
