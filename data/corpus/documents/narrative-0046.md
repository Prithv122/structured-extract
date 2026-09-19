The `odbc.ini` file contains the DSNs for the drivers, which can have specific knobs.
An example of `odbc.ini` with DuckDB:

```ini
[DuckDB]
Driver = DuckDB Driver
Database = :memory:
access_mode = read_only
```

The lines correspond to the following parameters:

* `[DuckDB]`: between the brackets is a DSN for the DuckDB.
* `Driver`: Describes the driver's name, as well as where to find the configurations in the `odbcinst.ini`.
* `Database`: Describes the database name used by DuckDB, can also be a file path to a `.db` in the system.
* `access_mode`: The mode in which to connect to the database.
