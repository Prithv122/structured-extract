### Global Configuration Options

|                     Name                      |                                                                                                  Description                                                                                                  |    Type     |                    Default value                    |
|----|--------|--|---|
| `write_buffer_row_group_count`                | The amount of row groups to buffer in bulk ingestion prior to flushing them together. Reducing this setting can reduce memory consumption.                                                                    | `UBIGINT`   | `5`                                                 |
