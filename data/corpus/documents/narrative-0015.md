Core DuckDB sets the default user-agent as follows:

```text
duckdb/v1.4.4(osx_arm64) cli 6ddac802ff
```

which indicates version, architecture, client, buildref in the agent string. The user-agent string can also be modified via the `custom_user_agent` setting, see [Configuration]({% link docs/current/configuration/overview.md %}). The currently generated user-agent string can be seen via `PRAGMA user_agent;`, see [Configuration/Pragmas]({% link docs/current/configuration/pragmas.md %}#user-agent).

In addition, some extensions set their own user agents; notable examples here include the following.
