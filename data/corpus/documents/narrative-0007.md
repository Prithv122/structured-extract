> Warning This feature is experimental.

By default, `VACUUM` skips tables that have ART indexes. The `vacuum_rebuild_indexes` setting enables vacuum to compact row groups on tables with indexes by rebuilding the indexes afterward. The setting specifies a row count threshold: tables exceeding the threshold are skipped. Set to `0` to disable (the default).

```sql
SET vacuum_rebuild_indexes = 1000000;
```
