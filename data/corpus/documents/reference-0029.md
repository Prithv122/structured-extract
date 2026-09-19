### Global Configuration Options

|                     Name                      |                                                                                                  Description                                                                                                  |    Type     |                    Default value                    |
|----|--------|--|---|
| `index_scan_max_count`                        | The maximum index scan count sets a threshold for index scans. If fewer than MAX(index_scan_max_count, index_scan_percentage * total_row_count) rows match, we perform an index scan instead of a table scan. | `UBIGINT`   | `2048`                                              |
