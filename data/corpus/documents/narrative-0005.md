The same options can be appended to the JDBC URL, separated by semicolons. This is the only way to configure DuckDB in tools that accept a connection string but no `Properties` object:

```text
jdbc:duckdb:/tmp/my_database;threads=4;memory_limit=4GB;jdbc_stream_results=true
```

Each entry is a `key=value` pair and surrounding whitespace is trimmed. The driver splits the URL on `;` and each entry on `=`, so a value that itself contains a semicolon or an equals sign has to be passed in a `Properties` object instead.
