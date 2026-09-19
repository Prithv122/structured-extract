By default, a long-running query re-reads an object at whatever version is current at read time, which can change if the object is overwritten. Set `s3_version_id_pinning` (`BOOLEAN`, default `false`) to pin reads to the object version captured on the first `HEAD` request, so a query sees a consistent version even if the object is overwritten mid-query. This requires the HTTP metadata cache:

```sql
SET enable_http_metadata_cache = true;
SET s3_version_id_pinning = true;
```
