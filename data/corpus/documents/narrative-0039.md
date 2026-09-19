The `session_init_sql_file` option points the driver at a SQL file on the local file system that is executed before the connection is returned to the caller. It is intended for environments where you control the connection string but not the code that opens the connection, for example a BI tool that only offers a JDBC URL field:

```text
jdbc:duckdb:/tmp/my_database;session_init_sql_file=/path/to/init.sql
```

The file can be split into a database part and a connection part with a marker comment:

```sql
-- Runs once, when the database instance is created.
SET memory_limit = '4GB';
CREATE OR REPLACE VIEW recent_events AS
    SELECT *
    FROM events
    WHERE ts > now() - INTERVAL 7 DAYS;

/* DUCKDB_CONNECTION_INIT_BELOW_MARKER */

-- Runs for every connection.
SET search_path = 'analytics';
```

Everything above the marker runs the first time the database is opened in the JVM process, and everything below it runs for every connection. A file without a marker is treated entirely as database initialization. For the unnamed in-memory database the database part runs for every connection, because each connection gets its own instance.

Because the option makes the connection string execute arbitrary SQL, the driver constrains it:

* It is read from the JDBC URL only and is not picked up from a `Properties` object.
* It has to be the first option in the connection string, and `session_init_sql_file_sha256`, if present, has to be the second. Neither may appear more than once.
* The file may not be larger than 1 MB.
* If `session_init_sql_file_sha256` is given and does not match the file's digest, opening the connection fails. Use it to detect a file that was modified after deployment.
* `DuckDBConnection.getSessionInitSQL()` returns the text that was executed, so an application can log or audit it.

> Warning The SQL in the file runs with the full privileges of the connection. Treat the connection string and the file it points at as trusted input.
