Structured log of every Quack message (both client- and server-side):

```sql
CALL enable_logging('Quack');

FROM quack_query('quack:localhost', 'SELECT 42');

SELECT * FROM duckdb_logs_parsed('Quack');
```

<div class="monospace_table"></div>

<!-- markdownlint-disable MD034 -->

| context_id | scope      | connection_id | transaction_id | query_id | thread_id | timestamp                     | type  | log_level | message_type       | quack_connection_id              | client_query_id | query     | server                | duration_ms | response_type       | error |
| ---------: | ---------- | ------------: | -------------: | -------: | --------: | ----------------------------- | ----- | --------- | ------------------ | -------------------------------- | --------------: | --------- | --------------------- | ----------: | ------------------- | ----- |
|         60 | CONNECTION |             2 |             18 |       18 |      NULL | 2026-05-10 09:06:19.841623+02 | Quack | DEBUG     | CONNECTION_REQUEST |                                  |              18 | NULL      | http://localhost:9494 |          41 | CONNECTION_RESPONSE | NULL  |
|         60 | CONNECTION |             2 |             18 |       18 |      NULL | 2026-05-10 09:06:19.842407+02 | Quack | DEBUG     | PREPARE_REQUEST    | 091A003553E7E67B615B73D6BE81FD2E |              18 | SELECT 42 | http://localhost:9494 |           0 | PREPARE_RESPONSE    | NULL  |

<!-- markdownlint-enable MD034 -->

Fields on each entry:

| Field                 | Description                                                           |
| --------------------- | --------------------------------------------------------------------- |
| `message_type`        | Request type: `PREPARE_REQUEST`, `FETCH_REQUEST`, etc.                |
| `quack_connection_id` | Server-issued connection id (stable across requests in one `ATTACH`). |
| `client_query_id`     | Monotonic id assigned by the client, correlates client / server logs. |
| `query`               | SQL payload for `PREPARE_REQUEST`s.                                   |
| `server`              | HTTP URL on client-side logs, `NULL` on server-side logs.             |
| `duration_ms`         | Round-trip time (client) or handling time (server).                   |
| `response_type`       | Response type  or `ERROR`.                                            |
| `error`               | Error message if the request failed.                                  |

To correlate a client request with its server-side handling, join on `(quack_connection_id, client_query_id)`.
