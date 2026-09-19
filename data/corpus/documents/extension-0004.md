Some additional configuration options exist for the S3 upload, though the default values should suffice for most use cases.

Additionally, most of the configuration options can be set via environment variables:

| DuckDB setting         | Environment variable       | Note                                     |
|:-----------------------|:---------------------------|:-----------------------------------------|
| `s3_region`            | `AWS_REGION`               | Takes priority over `AWS_DEFAULT_REGION` |
| `s3_region`            | `AWS_DEFAULT_REGION`       |                                          |
| `s3_access_key_id`     | `AWS_ACCESS_KEY_ID`        |                                          |
| `s3_secret_access_key` | `AWS_SECRET_ACCESS_KEY`    |                                          |
| `s3_session_token`     | `AWS_SESSION_TOKEN`        |                                          |
| `s3_endpoint`          | `DUCKDB_S3_ENDPOINT`       |                                          |
| `s3_use_ssl`           | `DUCKDB_S3_USE_SSL`        |                                          |
| `s3_requester_pays`    | `DUCKDB_S3_REQUESTER_PAYS` |                                          |
