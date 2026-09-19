Tables can be partitioned with the `PARTITIONED BY` clause using the [Iceberg partition transforms](https://iceberg.apache.org/spec/#partition-transforms):

| Transform | Description |
| --- | --- |
| `⟨column⟩`{:.language-sql .highlight} | Identity – partition by the column value directly. |
| `year(⟨column⟩)`{:.language-sql .highlight}, `month(⟨column⟩)`{:.language-sql .highlight}, `day(⟨column⟩)`{:.language-sql .highlight}, `hour(⟨column⟩)`{:.language-sql .highlight} | Partition by a date/timestamp component. |
| `bucket(⟨n⟩, ⟨column⟩)`{:.language-sql .highlight} | Hash the column into `n` buckets. |
| `truncate(⟨n⟩, ⟨column⟩)`{:.language-sql .highlight} | Truncate the column value to width `n`. |

```sql
CREATE TABLE my_catalog.sales.events (
    id INTEGER,
    event_name VARCHAR,
    event_time TIMESTAMP
)
PARTITIONED BY (day(event_time), bucket(16, id));
```

The partition spec can be changed on an existing table with `ALTER TABLE ... SET PARTITIONED BY`:

```sql
ALTER TABLE my_catalog.sales.events SET PARTITIONED BY (month(event_time));
```

> The `write.target-file-size-bytes` and `write.parquet.row-group-size-bytes` table properties are not honored for partitioned tables and raise an error. Set [`ignore_target_file_size_for_partitioned_tables`]({% link docs/current/core_extensions/iceberg/reference.md %}#settings) or `ignore_row_group_size_for_partitioned_tables` to `true` to ignore them instead.
