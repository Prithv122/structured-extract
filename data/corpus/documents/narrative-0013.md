The underlying HTTP transport can be logged separately:

```sql
CALL enable_logging('HTTP');
FROM quack_query('quack:localhost', 'SELECT 1');
SELECT request.type, request.url, response.status
FROM duckdb_logs_parsed('HTTP');
```

<div class="monospace_table"></div>

<!-- markdownlint-disable MD034 -->

| type | url                         | status |
| ---- | --------------------------- | ------ |
| POST | http://localhost:9494/quack | OK_200 |
| POST | http://localhost:9494/quack | OK_200 |

<!-- markdownlint-enable MD034 -->

Requests are `POST`s to a `/quack` endpoint.
