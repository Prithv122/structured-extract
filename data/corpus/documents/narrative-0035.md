Update the `memory_limit` configuration value:

```sql
SET memory_limit = '10GB';
```

Configure the system to use `1` thread:

```sql
SET threads = 1;
```

Or use the `TO` keyword:

```sql
SET threads TO 1;
```

Change configuration option to default value:

```sql
RESET threads;
```

Retrieve configuration value:

```sql
SELECT current_setting('threads');
```

Set the default collation for the session:

```sql
SET SESSION default_collation = 'nocase';
```
