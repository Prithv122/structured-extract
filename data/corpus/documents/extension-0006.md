| Setting                          | Type      | Default | Description                                                                                      |
| -------------------------------- | --------- | ------- | ------------------------------------------------------------------------------------------------ |
| `unsafe_enable_version_guessing` | `BOOLEAN` | `false` | Allows the extension to guess the latest metadata version when no version or hint file is given. |
| `iceberg_default_format_version` | `INTEGER` | `2` | Sets the default format_version to use when creating a new table. |
| `iceberg_unsafe_skip_puffin_verification` | `BOOLEAN` | `false` | When reading V3 Deletion Vectors, skip the Puffin file verification (for compatibility with files written by older versions). |
