Cast a connection to `DuckDBConnection` and call `getProfilingInformation(ProfilerPrintFormat)` to retrieve profiling output for the most recent query on that connection, after enabling profiling with `PRAGMA enable_profiling`. The `ProfilerPrintFormat` enum selects the output format: `DEFAULT`, `TEXT`, `QUERY_TREE`, `QUERY_TREE_OPTIMIZER`, `NO_OUTPUT`, `JSON`, `HTML`, `GRAPHVIZ`, `YAML`, and `MERMAID`.

```java
try (DuckDBConnection conn = (DuckDBConnection) DriverManager.getConnection("jdbc:duckdb:");
     Statement stmt = conn.createStatement()) {
    stmt.execute("PRAGMA enable_profiling = 'json'");
    stmt.executeQuery("SELECT count(*) FROM range(1000)").close();
    String profile = conn.getProfilingInformation(ProfilerPrintFormat.JSON);
    System.out.println(profile);
}
```
