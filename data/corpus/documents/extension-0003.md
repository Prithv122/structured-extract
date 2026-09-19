| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `unsafe_enable_version_guessing` | `BOOLEAN` | `false` | Enable globbing the filesystem (if possible) to find the latest metadata version. This may read an uncommitted version, so it is disabled by default. |
| `iceberg_use_metadata_log` | `BOOLEAN` | `true` | Use a table's optional `metadata-log` to preserve atomicity guarantees, at the cost of an additional metadata `GET` in rare cases. |
| `ignore_target_file_size_for_partitioned_tables` | `BOOLEAN` | `false` | Ignore the unsupported `write.target-file-size-bytes` table property on partitioned tables instead of raising an error. |
| `ignore_row_group_size_for_partitioned_tables` | `BOOLEAN` | `false` | Ignore the unsupported `write.parquet.row-group-size-bytes` table property on partitioned tables instead of raising an error. |
| `iceberg_via_aws_sdk_for_catalog_interactions` | `BOOLEAN` | `false` | Use the legacy AWS SDK code path to interact with AWS-based catalogs instead of DuckDB's HTTP client. |
