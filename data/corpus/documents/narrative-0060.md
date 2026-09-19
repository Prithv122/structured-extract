JSON files can be read using the `read_json` function, called either from within Python or directly from within SQL. By default, the `read_json` function will automatically detect if a file contains newline-delimited JSON or regular JSON, and will detect the schema of the objects stored within the JSON file.

Read from a single JSON file:

```python
duckdb.read_json("example.json")
```

Read multiple JSON files from a folder:

```python
duckdb.read_json("folder/*.json")
```

Directly read a JSON file from within SQL:

```python
duckdb.sql("SELECT * FROM 'example.json'")
```

Call `read_json` from within SQL:

```python
duckdb.sql("SELECT * FROM read_json('example.json')")
```
