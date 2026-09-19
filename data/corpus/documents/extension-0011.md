The `delta` extension adds the following settings:

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `delta_kernel_logging` | `BOOLEAN` | `false` | Forward the internal logging of the [Delta Kernel](https://github.com/delta-incubator/delta-kernel-rs) to the DuckDB logger. May impact performance even when DuckDB logging is disabled. |
| `delta_scan_explain_files_filtered` | `BOOLEAN` | `true` | Add the filtered files to the `EXPLAIN` output. May impact the performance of `delta_scan` during `EXPLAIN ANALYZE` queries. |
