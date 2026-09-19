A REST Catalog with OAuth2 authorization can also be attached with just an `ATTACH` statement. See the complete list of `ATTACH` options for a REST Catalog below.

| Parameter                            | Type       | Default              | Description                                                                                                                                                             |
| ------------------------------------ | ---------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ENDPOINT_TYPE`                      | `VARCHAR`  | `NULL`               | Used for attaching S3 Tables or Glue catalogs. Allowed values are `GLUE` and `S3_TABLES`. Cannot be combined with `ENDPOINT` or `AUTHORIZATION_TYPE`.                  |
| `ENDPOINT`                           | `VARCHAR`  | `NULL`               | URL endpoint to communicate with the REST Catalog. Cannot be used in conjunction with `ENDPOINT_TYPE`.                                                                 |
| `SECRET`                             | `VARCHAR`  | `NULL`               | Name of the secret used to communicate with the REST Catalog.                                                                                                          |
| `CLIENT_ID`                          | `VARCHAR`  | `NULL`               | `CLIENT_ID` used for the secret.                                                                                                                                       |
| `CLIENT_SECRET`                      | `VARCHAR`  | `NULL`               | `CLIENT_SECRET` used for the secret.                                                                                                                                   |
| `DEFAULT_REGION`                     | `VARCHAR`  | `NULL`               | Default region to use when communicating with the storage layer.                                                                                                      |
| `DEFAULT_SCHEMA`                     | `VARCHAR`  | `NULL`               | The default schema (namespace) to use for the attached catalog.                                                                                                       |
| `OAUTH2_SERVER_URI`                  | `VARCHAR`  | `NULL`               | OAuth2 server URL for getting a Bearer token.                                                                                                                          |
| `AUTHORIZATION_TYPE`                 | `VARCHAR`  | `OAUTH2`             | Authorization scheme. Pass `SigV4` for catalogs that require SigV4 authorization, or `none` for catalogs that need no authentication. Cannot be combined with `ENDPOINT_TYPE`. |
| `ACCESS_DELEGATION_MODE`             | `VARCHAR`  | `vended_credentials` | Access delegation mode. Allowed values are `vended_credentials` and `none`.                                                                                            |
| `EXTRA_HTTP_HEADERS`                 | `MAP`      | `NULL`               | Additional HTTP headers to send with REST Catalog requests.                                                                                                            |
| `SUPPORT_NESTED_NAMESPACES`          | `BOOLEAN`  | `false`              | Set to `true` for catalogs that support nested namespaces.                                                                                                             |
| `STAGE_CREATE_TABLES`                | `BOOLEAN`  | `true`               | Controls whether DuckDB uses staged `CREATE TABLE`. Disable for catalogs that do not support staged table creation.                                                    |
| `DISABLE_MULTI_TABLE_COMMIT`         | `BOOLEAN`  | `false`              | Disables the multi-table transactions/commit endpoint. Enable for catalogs that reject this endpoint.                                                                  |
| `SKIP_CREATE_TABLE_METADATA_UPDATES` | `BOOLEAN`  | `false`              | Skips follow-up metadata updates after non-staged `CREATE TABLE`. Enable for catalogs that fully initialize metadata during table creation and reject subsequent updates. |
| `REMOVE_FILES_ON_DELETE`             | `BOOLEAN`  | `true`               | Controls whether DuckDB removes storage files when a table is dropped.                                                                                                 |
| `PURGE_REQUESTED`                    | `BOOLEAN`  | `false`              | Sends the [PurgeRequested](https://github.com/apache/iceberg/blob/4b4eb38cf6dda7b43faeb40eb00aa5db424d2ecb/open-api/rest-catalog-open-api.yaml#L1144) parameter when dropping a table. |
| `ENCODE_ENTIRE_PREFIX`               | `BOOLEAN`  | `false`              | URL-encode the entire path prefix when communicating with the catalog.                                                                                                 |
| `MAX_TABLE_STALENESS`                | `INTERVAL` | `NULL`               | Prevents unnecessary requests to the Iceberg REST Catalog. Accepts human-readable interval strings such as `10 minutes`, `30 seconds`, or `1 year`.                    |

> When attaching an AWS catalog with `ENDPOINT_TYPE` (`s3_tables` or `glue`), DuckDB applies AWS-appropriate defaults: `stage_create_tables` and `remove_files_on_delete` become `false` and `purge_requested` becomes `true`, unless you set them explicitly.

The following options can only be passed to a `CREATE SECRET` statement and they require `AUTHORIZATION_TYPE` to be `OAUTH2`:

| Parameter           | Type      | Default | Description                                          |
| ------------------- | --------- | ------- | ---------------------------------------------------- |
| `OAUTH2_GRANT_TYPE` | `VARCHAR` | `NULL`  | Grant Type when requesting an OAuth Token.           |
| `OAUTH2_SCOPE`      | `VARCHAR` | `NULL`  | Requested scope for the returned OAuth Access Token. |
