By default, each Quack client request opens a fresh connection to the server — a new TCP and, with SSL, a costly TLS handshake. Connection caching reuses connections across requests, reducing per-query latency on repeated requests:

{:.codebox-client}
```sql
SET httpfs_connection_caching = true;
```
