To retrieve the home directory's path from the `HOME` environment variable, use:

```sql
SELECT getenv('HOME') AS home;
```

|       home       |
|------------------|
| /Users/user_name |

The output of the `getenv` function can be used to set [configuration options]({% link docs/current/configuration/overview.md %}). For example, to set the `NULL` order based on the environment variable `DEFAULT_NULL_ORDER`, use:

```sql
SET default_null_order = getenv('DEFAULT_NULL_ORDER');
```
