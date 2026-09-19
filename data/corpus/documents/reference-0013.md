### Global Configuration Options

|                     Name                      |                                                                                                  Description                                                                                                  |    Type     |                    Default value                    |
|----|--------|--|---|
| `write_buffer_row_group_memory_limit`         | The maximum data to buffer in row groups (in bytes) prior to flushing them together. When either this limit or `write_buffer_row_group_count` is reached, the data is flushed to disk. Defaults to 20% of the memory limit divided by the thread count. | `VARCHAR`   |                                                     |
