# Hand-labelling worksheet

45 prose sections drawn from the 85 in the corpus, seeded and
stratified. The reference stratum is excluded: those 35 documents are single
rows of the generated configuration reference table and already have exact
ground truth.

**Read here, write in `data/labels/recall_labels.jsonl`.** For each document set
`documents` to the list of settings that section *documents*, and move anything
merely mentioned into `cross_referenced`. `documents: []` is a real answer and
is expected to be common. `documents: null` means not yet judged.

The question is only *which settings*. Type, scope and default are not asked:
the oracle and the reference table already know them for any name you give.

---

## [x] `extension-0001`  ·  extension-signal

- source: `core_extensions/aws.md`
- heading: AWS Extension > Installing and Loading > `credential_chain` Provider > Region Resolution
- names the detector found: `s3_region`

```markdown
If no region is provided explicitly, DuckDB resolves it from the following sources, in order:

1. The `REGION` secret parameter.
2. The `s3_region` [setting]({% link docs/current/configuration/overview.md %}) (`SET s3_region = '⟨region⟩'`).
3. The `AWS_REGION` environment variable.
4. The `AWS_DEFAULT_REGION` environment variable.
5. The `region` of the profile in `~/.aws/config`.

If none of these resolve, `CREATE SECRET` still succeeds, but DuckDB logs a warning:

```console
Set region explicitly using REGION 'us-east-1' in your CREATE SECRET statement, adding a region to your profile in ~/.aws/config or configure the AWS_REGION or AWS_DEFAULT_REGION environment variables.
```
```

## [ ] `extension-0002`  ·  extension-signal

- source: `core_extensions/iceberg/overview.md`
- heading: Iceberg Extension > Installing and Loading > Reading Iceberg Tables > “Guessing” Metadata Versions
- names the detector found: `unsafe_enable_version_guessing`

```markdown
By default, either a table version number or a `version-hint.text` **must** be provided for the `iceberg` extension to read a table. This is typically provided by an external data catalog. In the event neither is present, the `iceberg` extension can attempt to guess the latest version by passing `?` as the `version` parameter:

```sql
SELECT count(*)
FROM iceberg_scan(
    'data/iceberg/lineitem_iceberg_no_hint',
    version = '?',
    allow_moved_paths = true
);
```

The “latest” version is assumed to be the filename that is lexicographically largest when sorting the filenames. Collations are not considered. This behavior is not enabled by default as it may potentially violate ACID constraints. It can be enabled by setting `unsafe_enable_version_guessing` to `true`. When this is set, `iceberg` functions will attempt to guess the latest version by default before failing.

```sql
SET unsafe_enable_version_guessing = true;
SELECT count(*)
FROM iceberg_scan(
    'data/iceberg/lineitem_iceberg_no_hint',
    allow_moved_paths = true
);
```
```

## [x] `extension-0003`  ·  extension-signal

- source: `core_extensions/postgres/connection_pool.md`
- heading: PostgreSQL Extension Connection Pool > Parallel Scans > Thread-local Cache
- names the detector found: `pg_pool_enable_thread_local_cache`, `threads`

```markdown
Idle connection in a pool are available for any caller thread, be it a DuckDB internal worker thread or a new client thread. In some cases it may be beneficial to ensure, that subsequent queries from the same thread are run on the same connection as the first query.
To support this the `pg_pool_enable_thread_local_cache` configuration option can be used - it makes an idle connection to be returned to a thread-local (and thread-private) cache instead of the main cache shared between all threads.

> Warning 
> Thread-local connection are not checked and not cleaned up by the reaper thread. Thread-local cache should be used with caution as cached connections, while not available to other threads, are still take the place in the pool, so can cause a "pool startvation".
```

## [x] `extension-0005`  ·  extension-signal

- source: `core_extensions/postgres/overview.md`
- heading: PostgreSQL Extension > Installing and Loading > Schema Cache
- names the detector found: `pg_staleness_query`, `pg_staleness_query_enabled`, `schema`

```markdown
To avoid having to continuously fetch schema data from PostgreSQL, DuckDB keeps schema information – such as the names of tables, their columns, etc. – cached. If changes are made to the schema through a different connection to the PostgreSQL instance, such as new columns being added to a table, the cached schema information might be outdated. In this case, the function `pg_clear_cache` can be executed to clear the internal caches.

```sql
CALL pg_clear_cache();
```

In version 1.5.5 a support for automatic detection of schema changes was added using a "staleness query"
(contributed by Brandon Freeman in [duckdb/duckdb-postgres#514](https://github.com/duckdb/duckdb-postgres/pull/514)):

 - when `pg_staleness_query_enabled` option (`BOOLEAN`, default: `FALSE`) is enabled, on every catalog access a query is run that
   checks Postgres' `pg_class.xmin` column value in every table and reloads the cache automatically, if a change is detected

 - for Postgres-wire-compatible databases a custom "staleness query" can be set using `pg_staleness_query` option.
```

## [x] `extension-0006`  ·  extension-signal

- source: `core_extensions/iceberg/iceberg_options.md`
- heading: Iceberg Options > `ATTACH` Options > Settings
- names the detector found: `unsafe_enable_version_guessing`

```markdown
| Setting                          | Type      | Default | Description                                                                                      |
| -------------------------------- | --------- | ------- | ------------------------------------------------------------------------------------------------ |
| `unsafe_enable_version_guessing` | `BOOLEAN` | `false` | Allows the extension to guess the latest metadata version when no version or hint file is given. |
| `iceberg_default_format_version` | `INTEGER` | `2` | Sets the default format_version to use when creating a new table. |
| `iceberg_unsafe_skip_puffin_verification` | `BOOLEAN` | `false` | When reading V3 Deletion Vectors, skip the Puffin file verification (for compatibility with files written by older versions). |
```

## [x] `extension-0008`  ·  extension-signal

- source: `core_extensions/jemalloc.md`
- heading: jemalloc Extension > Operating System Support > Configuration > Background Threads
- names the detector found: `allocator_background_threads`, `threads`

```markdown
By default, jemalloc's [background threads](https://jemalloc.net/jemalloc.3.html#background_thread) are disabled. To enable them, use the following configuration option:

```sql
SET allocator_background_threads = true;
```

Background threads asynchronously purge outstanding allocations so that this doesn't have to be done synchronously by the foreground threads. This improves allocation performance, and should be noticeable in allocation-heavy workloads, especially on many-core CPUs.
```

## [x] `extension-0012`  ·  extension-signal

- source: `core_extensions/spatial/r-tree_indexes.md`
- heading: R-Tree Indexes > Why Should I Use an R-Tree Index? > Performance Considerations > Memory Usage
- names the detector found: `max_memory`

```markdown
Like DuckDB's built in ART-index, all the associated buffers containing the R-tree will be lazily loaded from disk (when running DuckDB in disk-backed mode), but they are currently never unloaded unless the index is dropped. This means that if you end up scanning the entire index, the entire index will be loaded into memory and stay there for the duration of the database connection. However, all memory used by the R-tree index (even during bulk-loading) is tracked by DuckDB, and will count towards the memory limit set by the `memory_limit` configuration parameter.
```

## [x] `extension-0014`  ·  extension-signal

- source: `core_extensions/httpfs/s3api_legacy_authentication.md`
- heading: Legacy Authentication Scheme for S3 API > Legacy Authentication Scheme
- names the detector found: `s3_access_key_id`, `s3_endpoint`, `s3_region`, `s3_secret_access_key`, `s3_session_token`, `s3_url_style`, `s3_use_ssl`

```markdown
To be able to read or write from S3, the correct region should be set:

```sql
SET s3_region = 'us-east-1';
```

Optionally, the endpoint can be configured in case a non-AWS object storage server is used:

```sql
SET s3_endpoint = '⟨domain⟩.⟨tld⟩:⟨port⟩';
```

If the endpoint is not SSL-enabled then run:

```sql
SET s3_use_ssl = false;
```

Switching between [path-style](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html#path-style-access) and [vhost-style](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html#virtual-hosted-style-access) URLs is possible using:

```sql
SET s3_url_style = 'path';
```

However, note that this may also require updating the endpoint. For example for AWS S3 it is required to change the endpoint to `s3.⟨region⟩.amazonaws.com`{:.language-sql .highlight}.

After configuring the correct endpoint and region, public files can be read. To also read private files, authentication credentials can be added:

```sql
SET s3_access_key_id = '⟨aws_access_key_id⟩';
SET s3_secret_access_key = '⟨aws_secret_access_key⟩';
```

Alternatively, temporary S3 credentials are also supported. They require setting an additional session token:

```sql
SET s3_session_token = '⟨aws_session_token⟩';
```

The [`aws` extension]({% link docs/current/core_extensions/aws.md %}) allows for loading AWS credentials.
```

## [x] `extension-0015`  ·  extension-signal

- source: `core_extensions/mysql.md`
- heading: MySQL Extension > Installing and Loading > Settings
- names the detector found: `mysql_bit1_as_boolean`, `mysql_debug_show_queries`, `mysql_enable_transactions`, `mysql_incomplete_dates_as_nulls`, `mysql_pool_acquire_mode`, `mysql_pool_connection_idle_timeout_millis`, `mysql_pool_connection_max_lifetime_millis`, `mysql_pool_enable_reaper_thread`, `mysql_pool_enable_thread_local_cache`, `mysql_pool_size`, `mysql_pool_wait_timeout_millis`, `mysql_session_time_zone`, `mysql_time_as_time`, `mysql_tinyint1_as_boolean`

```markdown
| Name | Description | Default |
|------|-------------|---------|
| `mysql_bit1_as_boolean` | Whether or not to convert `BIT(1)` columns to `BOOLEAN` | `true` |
| `mysql_debug_show_queries` | DEBUG SETTING: print all queries sent to MySQL to stdout | `false` |
| `mysql_enable_filter_pushdown` | Whether or not to use filter pushdown (without predicate analyzer) | `true` |
| `mysql_enable_transactions` | Whether to run `START TRANSACTION` / `COMMIT` / `ROLLBACK` on MySQL connections | `true` |
| `mysql_incomplete_dates_as_nulls` | Whether to return `DATE`s with a zero month or day as `NULL`s | `false` |
| `mysql_pool_acquire_mode` | How to acquire connections from the pool: `force` (always connect, ignoring the pool limit), `wait` (block until one is available), or `try` (fail immediately if none is available) | `force` |
| `mysql_pool_connection_idle_timeout_millis` | Maximum time in milliseconds a connection can sit idle in the cache before being closed | `60000` |
| `mysql_pool_connection_max_lifetime_millis` | Maximum age in milliseconds of a pooled connection since it was first opened; when exceeded, the connection is closed instead of being returned to the cache (`0` disables it) | `0` |
| `mysql_pool_enable_reaper_thread` | Whether to run a dedicated thread that periodically scans the pool and removes expired connections | `true` |
| `mysql_pool_enable_thread_local_cache` | Enable thread-local connection caching for faster same-thread connection reuse | `false` |
| `mysql_pool_size` | Maximum number of connections per MySQL catalog | automatic (based on the CPU count) |
| `mysql_pool_wait_timeout_millis` | Timeout in milliseconds when waiting for a connection from the pool | `30000` |
| `mysql_session_time_zone` | Session time zone to set for newly opened connections to the MySQL server | `''` |
| `mysql_time_as_time` | Whether or not to convert MySQL's `TIME` columns to DuckDB's `TIME` | `false` |
| `mysql_tinyint1_as_boolean` | Whether or not to convert `TINYINT(1)` columns to `BOOLEAN` | `true` |
```

## [x] `extension-0016`  ·  extension-signal

- source: `extensions/installing_extensions.md`
- heading: Installing Extensions > Extension Repositories > Installing Extensions from Different Repositories
- names the detector found: `custom_extension_repository`

```markdown
To install extensions from the default repository (`core`), run:

```sql
INSTALL httpfs;
```

To explicitly install an extension from the core repository, run:

```sql
INSTALL httpfs FROM core;
-- or
INSTALL httpfs FROM 'http://extensions.duckdb.org';
```

To install an extension from the core nightly repository:

```sql
INSTALL spatial FROM core_nightly;
-- or
INSTALL spatial FROM 'http://nightly-extensions.duckdb.org';
```

To install an extension from a custom repository:

```sql
INSTALL ⟨custom_extension⟩ FROM 'https://my-custom-extension-repository';
```

Alternatively, the `custom_extension_repository` setting can be used to change the default repository used by DuckDB:

```sql
SET custom_extension_repository = 'http://nightly-extensions.duckdb.org';
```

DuckDB contains the following predefined repositories:

| Alias                 | URL                                      | Description                                                                            |
|:----------------------|:-----------------------------------------|:---------------------------------------------------------------------------------------|
| `core`                | `http://extensions.duckdb.org`           | DuckDB core extensions                                                                 |
| `core_nightly`        | `http://nightly-extensions.duckdb.org`   | Nightly builds for `core`                                                              |
| `community`           | `http://community-extensions.duckdb.org` | DuckDB community extensions                                                            |
| `local_build_debug`   | `./build/debug/repository`               | Repository created when building DuckDB from source in debug mode (for development)    |
| `local_build_release` | `./build/release/repository`             | Repository created when building DuckDB from source in release mode (for development)  |
```

## [ ] `extension-0020`  ·  extension-distractor

- source: `core_extensions/postgres/secrets.md`
- heading: PostgreSQL Extension and the Secret Manager > Managing Multiple Secrets > AWS RDS IAM Authentication
- names the detector found: `password`

```markdown
Managed PostgreSQL databases running on RDS/Aurora services allow to use [IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html).
In that case the authentication token is generated using AWS SDK and must be refreshed every 15 minutes.

The `postgres` extension supports IAM authentication, when the password is not specified in the secret, but instead one of the configured AWS Credential Providers is used to generate the password, that is refreshed by the `postgres` extension automatically.
```

## [x] `extension-0021`  ·  extension-distractor

- source: `core_extensions/ui.md`
- heading: UI Extension
- names the detector found: `username`

```markdown
The `ui` extension adds a user interface for your local DuckDB instance.

The UI is built and maintained by [MotherDuck](https://motherduck.com/).
An overview of its features can be found
in the [MotherDuck documentation](https://motherduck.com/docs/getting-started/motherduck-quick-tour/).
```

## [x] `extension-0022`  ·  extension-distractor

- source: `extensions/versioning_of_extensions.md`
- heading: Versioning of Extensions > Extension Versioning > In-Tree vs. Out-of-Tree
- names the detector found: `username`

```markdown
Originally, DuckDB extensions lived exclusively in the DuckDB main repository, `github.com/duckdb/duckdb`. These extensions are called in-tree. Later, the concept
of out-of-tree extensions was added, where extensions were separated into their own repository, which we call out-of-tree.

While from a user's perspective, there are generally no noticeable differences, there are some minor differences related to versioning:

* in-tree extensions use the version of DuckDB instead of having their own version
* in-tree extensions do not have dedicated release notes, their changes are reflected in the regular [DuckDB release notes](https://github.com/duckdb/duckdb/releases)
* core out-of tree extensions tend to live in repositories named `github.com/duckdb/duckdb-⟨extension_name⟩`{:.language-sql .highlight} but the name may vary. See the [full list]({% link docs/current/core_extensions/overview.md %}) of core extensions for details.
```

## [x] `extension-0024`  ·  extension-distractor

- source: `core_extensions/ducklake.md`
- heading: DuckLake > Installing and Loading > Functions > `ducklake_snapshots`
- names the detector found: `schema`

```markdown
Returns the snapshots stored in the DuckLake catalog name `catalog`.

| Parameter name | Parameter type | Named parameter | Description |
| -------------- | -------------- | --------------- | ----------- |
| `catalog`      | `VARCHAR`      | no              |             |

The information is encoded into a table with the following schema:

| Column name      | Column type                |
| ---------------- | -------------------------- |
| `snapshot_id`    | `BIGINT`                   |
| `snapshot_time`  | `TIMESTAMP WITH TIME ZONE` |
| `schema_version` | `BIGINT`                   |
| `changes`        | `MAP(VARCHAR, VARCHAR[])`  |
```

## [ ] `narrative-0001`  ·  narrative-signal

- source: `sql/statements/copy.md`
- heading: COPY Statement > Examples > `COPY ... TO` > `COPY ... TO` Options
- names the detector found: `preserve_insertion_order`

```markdown
Zero or more copy options may be provided as a part of the copy operation. The `WITH` specifier is optional, but if any options are specified, the parentheses are required. Parameter values can be passed in with or without wrapping in single quotes. Arbitrary expressions may be used for parameter values.

Any option that is a Boolean can be enabled or disabled in multiple ways. You can write `true`, `ON`, or `1` to enable the option, and `false`, `OFF`, or `0` to disable it. The `BOOLEAN` value can also be omitted, e.g., by only passing `(HEADER)`, in which case `true` is assumed.

With few exceptions, the below options are applicable to all formats written with `COPY`.

| Name | Description | Type | Default |
|:--|:-----|:-|:-|
| `FORMAT` | Specifies the copy function to use. The default is selected from the file extension (e.g., `.parquet` results in a Parquet file being written/read). If the file extension is unknown `CSV` is selected. Vanilla DuckDB provides `CSV`, `PARQUET` and `JSON` but additional copy functions can be added by [`extensions`]({% link docs/current/extensions/overview.md %}). | `VARCHAR` | `auto` |
| `USE_TMP_FILE` | Whether or not to write to a temporary file first if the original file exists (`target.csv.tmp`). This prevents overwriting an existing file with a broken file in case the writing is cancelled. | `BOOL` | `auto` |
| `OVERWRITE_OR_IGNORE` | Whether or not to allow overwriting files if they already exist. Only has an effect when used with options that write multiple files, such as `PARTITION_BY`, `PER_THREAD_OUTPUT` or `FILE_SIZE_BYTES`. | `BOOL` | `false` |
| `OVERWRITE` | When `true`, all existing files inside targeted directories will be removed (not supported on remote filesystems). Only has an effect when used with options that write multiple files, such as `PARTITION_BY`, `PER_THREAD_OUTPUT` or `FILE_SIZE_BYTES`. | `BOOL` | `false` |
| `APPEND` | When `true`, in the event a filename pattern is generated that already exists, the path will be regenerated to ensure no existing files are overwritten. Only has an effect when used with options that write multiple files, such as `PARTITION_BY`, `PER_THREAD_OUTPUT` or `FILE_SIZE_BYTES`. | `BOOL` | `false` |
| `FILENAME_PATTERN` | Set a pattern to use for the filename, can optionally contain `{uuid}` / `{uuidv4}` or `{uuidv7}` to be filled in with a generated [UUID]({% link docs/current/sql/data_types/numeric.md %}#universally-unique-identifiers-uuids) (v4 or v7, respectively), and `{i}`, which is replaced by an incrementing index. Only has an effect when used with options that write multiple files, such as `PARTITION_BY`, `PER_THREAD_OUTPUT` or `FILE_SIZE_BYTES`. | `VARCHAR` | `auto` |
| `FILE_EXTENSION` | Set the file extension that should be assigned to the generated file(s). | `VARCHAR` | `auto` |
| `PER_THREAD_OUTPUT` | When `true`, the `COPY` command generates one file per thread, rather than one file in total. This allows for faster parallel writing. | `BOOL` | `false` |
| `FILE_SIZE_BYTES` | If this parameter is set, the `COPY` process creates a directory which will contain the exported files. If a file exceeds the set limit (specified as bytes such as `1000` or in human-readable format such as `1k`), the process creates a new file in the directory. This parameter works in combination with `PER_THREAD_OUTPUT`. Note that the size is used as an approximation, and files can be occasionally slightly over the limit. | `VARCHAR` or `BIGINT` | (empty) |
| `PARTITION_BY` | The columns to partition by using a Hive partitioning scheme, see the [partitioned writes section]({% link docs/current/data/partitioning/partitioned_writes.md %}). | `VARCHAR[]` | (empty) |
| `PRESERVE_ORDER` | Whether or not to [preserve order]({% link docs/current/sql/dialect/order_preservation.md %}) during the copy operation. Defaults to the value of the `preserve_insertion_order` [configuration option]({% link docs/current/configuration/overview.md %}). | `BOOL`| (*) |
| `RETURN_FILES` | Whether or not to include the created filepath(s) (as a `files VARCHAR[]` column) in the query result. | `BOOL` | `false` |
| `RETURN_STATS` | Whether or not to return the files and their column statistics that were written as part of the `COPY` statement. | `BOOL`| `false` |
| `WRITE_PARTITION_COLUMNS` | Whether or not to write partition columns into files. Only has an effect when used with `PARTITION_BY`. | `BOOL` | `false` |
```

## [ ] `narrative-0002`  ·  narrative-signal

- source: `clients/wasm/troubleshoot.md`
- heading: Troubleshoot > Overview > Extension Fails to Load from a Custom Repository
- names the detector found: `custom_extension_repository`

```markdown
DuckDB-Wasm fetches each extension over the network when it is loaded. If you serve extensions from a [custom repository]({% link docs/current/clients/wasm/deploying_duckdb_wasm.md %}#duckdb-extensions) with `SET custom_extension_repository = '⟨https://some.url.com⟩'`, the `GET` requests for the extension files must be [CORS enabled](https://www.w3.org/wiki/CORS_Enabled) for the browser to allow the connection, exactly as for remote data files above.

Extensions remain signed regardless of where they are served, so copying an extension to a different location keeps its signature valid.
```

## [x] `narrative-0003`  ·  narrative-signal

- source: `sql/expressions/collations.md`
- heading: Collations > Using Collations > Default Collations
- names the detector found: `default_collation`

```markdown
The collations we have seen so far have all been specified *per expression*. It is also possible to specify a default collator, either on the global database level or on a base table column. The `PRAGMA` `default_collation` can be used to specify the global default collator. This is the collator that will be used if no other one is specified.

```sql
SET default_collation = NOCASE;
SELECT 'hello' = 'HeLlo';
```

```text
true
```

Collations can also be specified per-column when creating a table. When that column is then used in a comparison, the per-column collation is used to perform that comparison.

```sql
CREATE TABLE names (name VARCHAR COLLATE NOACCENT);
INSERT INTO names VALUES ('hännes');
```

```sql
SELECT name
FROM names
WHERE name = 'hannes';
```

```text
hännes
```

Be careful here, however, as different collations cannot be combined. This can be problematic when you want to compare columns that have a different collation specified.

```sql
SELECT name
FROM names
WHERE name = 'hannes' COLLATE NOCASE;
```

```console
ERROR: Cannot combine types with different collation!
```

```sql
CREATE TABLE other_names (name VARCHAR COLLATE NOCASE);
INSERT INTO other_names VALUES ('HÄNNES');
```

```sql
SELECT names.name AS name, other_names.name AS other_name
FROM names, other_names
WHERE names.name = other_names.name;
```

```console
ERROR: Cannot combine types with different collation!
```

We need to manually overwrite the collation:

```sql
SELECT names.name AS name, other_names.name AS other_name
FROM names, other_names
WHERE names.name COLLATE NOACCENT.NOCASE = other_names.name COLLATE NOACCENT.NOCASE;
```

|  name  | other_name |
|--------|------------|
| hännes | HÄNNES     |
```

## [x] `narrative-0010`  ·  narrative-signal

- source: `sql/dialect/keywords_and_identifiers.md`
- heading: Keywords and Identifiers > Identifiers > Rules for Case-Sensitivity > Case-Sensitivity of Keys in Nested Data Structures > Disabling Preserving Cases
- names the detector found: `preserve_identifier_case`

```markdown
With the `preserve_identifier_case` [configuration option]({% link docs/current/configuration/overview.md %}#configuration-reference) set to `false`, all identifiers are turned into lowercase:

```sql
SET preserve_identifier_case = false;
CREATE TABLE tbl AS SELECT cos(pi()) AS CosineOfPi;
SELECT CosineOfPi FROM tbl;
```

| cosineofpi |
|-----------:|
| -1.0       |
```

## [x] `narrative-0012`  ·  narrative-signal

- source: `data/partitioning/partitioned_writes.md`
- heading: Partitioned Writes > Examples > Partitioned Writes
- names the detector found: `partitioned_write_max_open_files`

```markdown
When the `PARTITION_BY` clause is specified for the [`COPY` statement]({% link docs/current/sql/statements/copy.md %}), the files are written in a [Hive partitioned]({% link docs/current/data/partitioning/hive_partitioning.md %}) folder hierarchy. The target is the name of the root directory (in the example above: `orders`). The files are written in-order in the file hierarchy. Currently, one file is written per thread to each directory.

```text
orders
├── year=2021
│    ├── month=1
│    │   ├── data_1.parquet
│    │   └── data_2.parquet
│    └── month=2
│        └── data_1.parquet
└── year=2022
     ├── month=11
     │   ├── data_1.parquet
     │   └── data_2.parquet
     └── month=12
         └── data_1.parquet
```

The values of the partitions are automatically extracted from the data. Note that it can be very expensive to write a larger number of partitions as many files will be created. The ideal partition count depends on how large your dataset is.

To limit the maximum number of files the system can keep open before flushing to disk when writing using `PARTITION_BY`, use the `partitioned_write_max_open_files` configuration option (default: 100):

```batch
SET partitioned_write_max_open_files = 10;
```

> Bestpractice Writing data into many small partitions is expensive. It is generally recommended to have at least `100 MB` of data per partition.
```

## [x] `narrative-0013`  ·  narrative-signal

- source: `quack/reference.md`
- heading: Reference > Function Reference > Logging > HTTP Log
- names the detector found: `enable_logging`

```markdown
The underlying HTTP transport can be logged separately:

```sql
CALL enable_logging('HTTP');
FROM quack_query('quack:localhost', 'SELECT 1');
SELECT request.type, request.url, response.status
FROM duckdb_logs_parsed('HTTP');
```

<div class="monospace_table"></div>

<!-- markdownlint-disable MD034 -->

| type | url                         | status |
| ---- | --------------------------- | ------ |
| POST | http://localhost:9494/quack | OK_200 |
| POST | http://localhost:9494/quack | OK_200 |

<!-- markdownlint-enable MD034 -->

Requests are `POST`s to a `/quack` endpoint.
```

## [x] `narrative-0014`  ·  narrative-signal

- source: `sql/data_types/geometry.md`
- heading: Geometry Data Type > Types of Geometries > Geometry Storage > Shredding and Compression
- names the detector found: `geometry_minimum_shredding_size`

```markdown
The `GEOMETRY` type supports a storage optimization called "shredding", which improves compression for geometry columns where all values share the same geometry type and vertex dimensions.

When a row group qualifies, DuckDB splits the geometry segment within the row group into primitive `STRUCT`, `LIST`, and `DOUBLE` segments that can be compressed independently using lightweight algorithms - far more efficiently than storing variable-size binary blobs.

The shredded layout depends on the geometry type:

- `POINT` - STRUCT(X DOUBLE, Y DOUBLE) (and/or Z, M)
- `LINESTRING` - STRUCT(X DOUBLE, Y DOUBLE)[]
- `POLYGON` - STRUCT(X DOUBLE, Y DOUBLE)[][]
- `MULTIPOINT`, `MULTILINESTRING`, `MULTIPOLYGON` - same as above, with one additional level of list nesting
 
Row groups are not shredded if they contain `GEOMETRYCOLLECTION`s, any `EMPTY` geometries, or multiple geometry sub-types.

Additionally, row groups are not shredded if they fall below the minimum size threshold (default: ~25% of the maximum row group size, i.e., 30,000 rows).

This threshold is configurable via the `geometry_minimum_shredding_size` setting. Set it to `0` to always shred, or `-1` to disable shredding entirely.

```sql
-- Disable shredding for geometry columns
SET geometry_minimum_shredding_size = -1;

-- Always shred geometry columns regardless of row group size
SET geometry_minimum_shredding_size = 0;
```

The primary benefit of shredding is significantly improved compression, but in the future we plan to add ways to expose the shredded representation directly to the execution engine without having to "reassemble" the geometry back into binary again.

The following example illustrates the effects of shredding on the storage footprint of a `GEOMETRY` column.

```sql
-- Attach a persistent database with storage version v1.5
ATTACH 'geometry_db.db' as geometry_db (STORAGE_VERSION 'v1.5.0');

USE geometry_db;

-- Disable shredding completely and create a table with 1 million 2D points
SET geometry_minimum_shredding_size = -1;

CREATE OR REPLACE TABLE points AS SELECT printf('POINT (%d %d)', x, y)::GEOMETRY AS geom 
FROM range(0, 1000) AS rx(x), range(0, 1000) AS ry(y);

-- Checkpoint the database to persist the data and storage layout to disk
CHECKPOINT;

-- Attach a second database
ATTACH 'shredded_db.db' as shredded_db (STORAGE_VERSION 'v1.5.0');

USE shredded_db;

-- This time, set the minimum shredding size to 0 to always shred geometry columns,
-- and create the same table with 1 million 2D points
SET geometry_minimum_shredding_size = 0;

CREATE OR REPLACE TABLE points AS SELECT printf('POINT (%d %d)', x, y)::GEOMETRY AS geom 
FROM range(0, 1000) AS rx(x), range(0, 1000) AS ry(y);

-- Checkpoint to persist the data and storage layout to disk, and apply shredding
CHECKPOINT;

-- Now check the storage layout and memory usage of the geometry column in both attached databases
SELECT database_name, database_size FROM pragma_database_size();
----
┌───────────────┬───────────────┐
│ database_name │ database_size │
│    varchar    │    varchar    │
├───────────────┼───────────────┤
│ shredded_db   │ 2.2 MiB       │ -- Almost 3x smaller storage thanks to shredding!
│ geometry_db   │ 6.5 MiB       │ 
│ memory        │ 0 bytes       │
└───────────────┴───────────────┘

-- We can inspect what type of segments are used to store the geometry column 
-- in each database using the `pragma_storage_info` function. 

-- The geometry column in `geometry_db` is stored as regular GEOMETRY segments
SELECT DISTINCT(segment_type) FROM pragma_storage_info('geometry_db.points');
----
┌──────────────┐
│ segment_type │
│   varchar    │
├──────────────┤
│ GEOMETRY     │
│ VALIDITY     │
└──────────────┘

-- While the geometry column in `shredded_db` is decomposed into primitive DOUBLE segments,
-- which can be compressed much more efficiently!
SELECT DISTINCT(segment_type) FROM pragma_storage_info('shredded_db.points');
----
┌──────────────┐
│ segment_type │
│   varchar    │
├──────────────┤
│ VALIDITY     │
│ DOUBLE       │
└──────────────┘
```
```

## [x] `narrative-0015`  ·  narrative-signal

- source: `operations_manual/user_agents.md`
- heading: HTTP User-Agent
- names the detector found: `custom_user_agent`, `username`

```markdown
Core DuckDB sets the default user-agent as follows:

```text
duckdb/v1.4.4(osx_arm64) cli 6ddac802ff
```

which indicates version, architecture, client, buildref in the agent string. The user-agent string can also be modified via the `custom_user_agent` setting, see [Configuration]({% link docs/current/configuration/overview.md %}). The currently generated user-agent string can be seen via `PRAGMA user_agent;`, see [Configuration/Pragmas]({% link docs/current/configuration/pragmas.md %}#user-agent).

In addition, some extensions set their own user agents; notable examples here include the following.
```

## [x] `narrative-0017`  ·  narrative-signal

- source: `sql/query_syntax/with.md`
- heading: WITH Clause > Basic CTE Examples > Recursive CTEs with `USING KEY`
- names the detector found: `deprecated_using_key_syntax`

```markdown
> Deprecated DuckDB 1.5.0 deprecated the use of recursive `UNION`s for
> `USING KEY` CTEs in favor of recursive `UNION ALL`s.
> 
> The recursive `UNION`s imply that not all rows that are produced in one
> iteration are passed to the next, as would be the case for regular recursive
> CTEs. Since the opposite is true, i.e., all rows are passed from one iteration
> to the next, going forward DuckDB's `USING KEY` CTEs will require recursive
> `UNION ALL`s instead.
>
> DuckDB 1.5.0 also introduces a new setting to configure the `USING KEY` syntax.
>
> ```sql
> SET deprecated_using_key_syntax = 'DEFAULT';
> SET deprecated_using_key_syntax = 'UNION_AS_UNION_ALL';
> ```
>
> Currently, `DEFAULT` enables both syntax styles, i.e., allows both recursive
> `UNION`s and recursive `UNION ALL`s in `USING KEY` CTEs.
>
> DuckDB 1.5.0 will be the last release supporting the `UNION` syntax without
> explicitly enabling it.
>
> DuckDB 2.0.0 disables the `UNION` syntax by default.
>
> DuckDB 2.1.0 removes the `deprecated_using_key_syntax` flag and fully
> deprecates the `UNION` syntax.

`USING KEY` alters the behavior of a regular recursive CTE.

In each iteration, a regular recursive CTE appends result rows to the union table, which ultimately defines the overall result of the CTE. In contrast, a CTE with `USING KEY` has the ability to update rows that have been placed in the union table in an earlier iteration: if the current iteration produces a row with key `k`, it replaces a row with the same key `k` in the union table (like a dictionary). If no such row exists in the union table yet, the new row is appended to the union table as usual.

This allows a CTE to exercise fine-grained control over the union table contents. Avoiding the append-only behavior can lead to significantly smaller union table sizes. This helps query runtime, memory consumption, and makes it feasible to access the union table while the iteration is still ongoing. In a CTE `WITH RECURSIVE T(...) USING KEY ...`, table `T` denotes the rows added by the last iteration (as is usual for recursive CTEs), while table `recurring.T` denotes the [union table built so far](#accessing-the-union-table-with-recurring). References to `recurring.T` allow for the elegant and idiomatic translation of rather complex algorithms into readable SQL code.
```

## [x] `narrative-0019`  ·  narrative-signal

- source: `clients/wasm/extensions.md`
- heading: Load Extensions > Overview > Serving Extensions from a Third-Party Repository
- names the detector found: `custom_extension_repository`

```markdown
As with regular DuckDB, if you use `SET custom_extension_repository = 'https://some.url.com'`, subsequent loads will be attempted at `https://some.url.com/duckdb-wasm/$duckdb_version_hash/$duckdb_platform/$name.duckdb_extension.wasm`.

Note that `GET` requests for the extensions must be [CORS enabled](https://www.w3.org/wiki/CORS_Enabled) for a browser to allow the connection; see [Troubleshoot]({% link docs/current/clients/wasm/troubleshoot.md %}#extension-fails-to-load-from-a-custom-repository) if a load fails.
```

## [x] `narrative-0021`  ·  narrative-signal

- source: `internals/jemalloc.md`
- heading: jemalloc > Operating System Support > Configuration > Background Threads
- names the detector found: `allocator_background_threads`, `threads`

```markdown
By default, jemalloc's [background threads](https://jemalloc.net/jemalloc.3.html#background_thread) are disabled. To enable them, use the following configuration option:

```sql
SET allocator_background_threads = true;
```

Background threads asynchronously purge outstanding allocations so that this doesn't have to be done synchronously by the foreground threads. This improves allocation performance, and should be noticeable in allocation-heavy workloads, especially on many-core CPUs.
```

## [x] `narrative-0022`  ·  narrative-signal

- source: `configuration/pragmas.md`
- heading: Pragmas > Metadata > Implicit Casting to `VARCHAR`
- names the detector found: `old_implicit_casting`

```markdown
Prior to version 0.10.0, DuckDB would automatically allow any type to be implicitly cast to `VARCHAR` during function binding. As a result it was possible to e.g., compute the substring of an integer without using an explicit cast. For version v0.10.0 and later an explicit cast is needed instead. To revert to the old behavior that performs implicit casting, set the `old_implicit_casting` variable to `true`:

```sql
SET old_implicit_casting = true;
```
```

## [x] `narrative-0023`  ·  narrative-signal

- source: `guides/odbc/general.md`
- heading: ODBC 101: A Duck Themed Guide to ODBC > or > 2. Define the ODBC Handles and Connect to the Database > 2.a. Connecting with SQLConnect > 2.b. Connecting with SQLDriverConnect
- names the detector found: `access_mode`

```markdown
Alternatively, you can connect to the ODBC driver using [`SQLDriverConnect`](https://learn.microsoft.com/en-us/sql/odbc/reference/syntax/sqldriverconnect-function?view=sql-server-ver16).
`SQLDriverConnect` accepts a connection string in which you can configure the database using any of the available [DuckDB configuration options]({% link docs/current/configuration/overview.md %}).

```cpp
SQLHANDLE env;
SQLHANDLE dbc;

SQLAllocHandle(SQL_HANDLE_ENV, SQL_NULL_HANDLE, &env);

SQLSetEnvAttr(env, SQL_ATTR_ODBC_VERSION, (void*)SQL_OV_ODBC3, 0);

SQLAllocHandle(SQL_HANDLE_DBC, env, &dbc);

SQLCHAR str[1024];
SQLSMALLINT strl;
std::string dsn = "DSN=DuckDB;access_mode=READ_ONLY"
SQLDriverConnect(dbc, nullptr, (SQLCHAR*)dsn.c_str(), SQL_NTS, str, sizeof(str), &strl, SQL_DRIVER_COMPLETE)

std::cout << "Connected!" << std::endl;
```
```

## [x] `narrative-0025`  ·  narrative-signal

- source: `sql/data_types/timestamp.md`
- heading: Timestamp Types > Time Zones > Time Zone Support
- names the detector found: `TimeZone`

```markdown
The `TIMESTAMPTZ` type can be binned into calendar and clock bins using a suitable extension.
The built-in [ICU extension]({% link docs/current/core_extensions/icu.md %}) implements all the binning and arithmetic functions using the
[International Components for Unicode](https://icu.unicode.org) time zone and calendar functions.

To set the time zone to use, first load the ICU extension. The ICU extension comes pre-bundled with several DuckDB clients (including Python, R, JDBC and ODBC), so this step can be skipped in those cases. In other cases you might first need to install and load the ICU extension.

```sql
INSTALL icu;
LOAD icu;
```

Next, use the `SET TimeZone` command:

```sql
SET TimeZone = 'America/Los_Angeles';
```

Time binning operations for `TIMESTAMPTZ` will then be implemented using the given time zone.

A list of available time zones can be pulled from the `pg_timezone_names()` table function:

```sql
SELECT
    name,
    abbrev,
    utc_offset
FROM pg_timezone_names()
ORDER BY
    name;
```

You can also find a reference table of [available time zones]({% link docs/current/sql/data_types/timezones.md %}).
```

## [x] `narrative-0027`  ·  narrative-signal

- source: `sql/functions/utility.md`
- heading: Utility Functions > Scalar Utility Functions > Utility Table Functions
- names the detector found: `search_path`

```markdown
A [table function]({% link docs/current/sql/query_syntax/from.md %}#table-functions) is used in place of a table in a `FROM` clause.

| Name | Description |
|:--|:-------|
| [`glob(search_path)`](#globsearch_path) | Return filenames found at the location indicated by the *search_path* in a single column named `file`. The *search_path* may contain [glob pattern matching syntax]({% link docs/current/sql/functions/pattern_matching.md %}). |
| [`repeat_row(varargs, num_rows)`](#repeat_rowvarargs-num_rows) | Returns a table with `num_rows` rows, each containing the fields defined in `varargs`. |
```

## [x] `narrative-0028`  ·  narrative-signal

- source: `clients/rust/profiling.md`
- heading: Profile and Monitor > Overview > Further Reading
- names the detector found: `enable_profiling`, `profiling_mode`

```markdown
* [Profiling]({% link docs/current/dev/profiling.md %}) — DuckDB's query profiling output and the `enable_profiling` and `profiling_mode` PRAGMAs.
* [Run Queries]({% link docs/current/clients/rust/querying.md %}) — running the queries whose metrics this page reads and whose execution it interrupts.
* [Connect]({% link docs/current/clients/rust/connecting.md %}) — the `Connection` that profiling and the interrupt handle operate on.
```

## [x] `narrative-0030`  ·  narrative-signal

- source: `sql/data_types/typecasting.md`
- heading: Typecasting > Explicit Casting > Casting Operations Matrix
- names the detector found: `old_implicit_casting`

```markdown
Values of a particular data type cannot always be cast to any arbitrary target data type. The only exception is the `NULL` value – which can always be converted between types.
The following matrix describes which conversions are supported.
When implicit casting is allowed, it implies that explicit casting is also possible.

![Typecasting matrix](/images/typecasting-matrix.png)

Even though a casting operation is supported based on the source and target data type, it does not necessarily mean the cast operation will succeed at runtime.

> Deprecated Prior to version 0.10.0, DuckDB allowed any type to be implicitly cast to `VARCHAR` during function binding.
> Version 0.10.0 introduced a [breaking change which no longer allows implicit casts to `VARCHAR`]({% post_url 2024-02-13-announcing-duckdb-0100 %}#breaking-sql-changes).
> The [`old_implicit_casting` configuration option]({% link docs/current/configuration/pragmas.md %}#implicit-casting-to-varchar) setting can be used to revert to the old behavior.
> However, please note that this flag will be deprecated in the future.
```

## [x] `narrative-0031`  ·  narrative-signal

- source: `data/parquet/overview.md`
- heading: Reading and Writing Parquet Files > Examples > `read_parquet` Function > Parameters
- names the detector found: `binary_as_string`, `schema`

```markdown
There are a number of options exposed that can be passed to the `read_parquet` function or the [`COPY` statement]({% link docs/current/sql/statements/copy.md %}).

| Name | Description | Type | Default |
|:--|:-----|:-|:-|
| `binary_as_string` | Parquet files generated by legacy writers do not correctly set the `UTF8` flag for strings, causing string columns to be loaded as `BLOB` instead. Set this to true to load binary columns as strings. | `BOOL` | `false` |
| `can_have_nan` | Whether `FLOAT` and `DOUBLE` columns may contain `NaN` values. When set to true, the reader accounts for `NaN` when using a column's min/max statistics for filter pushdown, since `NaN` does not compare as ordered. | `BOOL` | `false` |
| `encryption_config` | Configuration for [Parquet encryption]({% link docs/current/data/parquet/encryption.md %}). | `STRUCT` | - |
| `filename` | Whether or not an extra `filename` column should be included in the result. Since DuckDB v1.3.0, the `filename` column is added automatically as a virtual column and this option is only kept for compatibility reasons. | `BOOL` | `false` |
| `file_row_number` | Whether or not to include the `file_row_number` column. | `BOOL` | `false` |
| `hive_partitioning` | Whether or not to interpret the path as a [Hive partitioned path]({% link docs/current/data/partitioning/hive_partitioning.md %}). | `BOOL` | (auto-detected) |
| `union_by_name` | Whether the columns of multiple schemas should be [unified by name]({% link docs/current/data/multiple_files/combining_schemas.md %}), rather than by position. | `BOOL` | `false` |
| `schema` | Allows you to read a Parquet file as if it has the supplied schema. Field IDs are required. | `MAP` | `NULL` |
```

## [x] `narrative-0032`  ·  narrative-signal

- source: `clients/odbc/configuration.md`
- heading: ODBC Configuration > `odbc.ini` and `.odbc.ini`
- names the detector found: `access_mode`

```markdown
The `odbc.ini` file contains the DSNs for the drivers, which can have specific knobs.
An example of `odbc.ini` with DuckDB:

```ini
[DuckDB]
Driver = DuckDB Driver
Database = :memory:
access_mode = read_only
```

The lines correspond to the following parameters:

* `[DuckDB]`: between the brackets is a DSN for the DuckDB.
* `Driver`: Describes the driver's name, as well as where to find the configurations in the `odbcinst.ini`.
* `Database`: Describes the database name used by DuckDB, can also be a file path to a `.db` in the system.
* `access_mode`: The mode in which to connect to the database.
```

## [x] `narrative-0034`  ·  narrative-signal

- source: `clients/r.md`
- heading: R Client > Summarize the dataset in DuckDB to avoid reading 12 Parquet files into R's memory > Memory Limit
- names the detector found: `max_memory`

```markdown
You can use the [`memory_limit` configuration option]({% link docs/current/configuration/pragmas.md %}) to limit the memory use of DuckDB, e.g.:

```sql
SET memory_limit = '2GB';
```

Note that this limit is only applied to the memory DuckDB uses and it does not affect the memory use of other R libraries.
Therefore, the total memory used by the R process may be higher than the configured `memory_limit`.
```

## [x] `narrative-0036`  ·  narrative-signal

- source: `sql/meta/duckdb_table_functions.md`
- heading: DuckDB_% Metadata Functions > `duckdb_columns` > `duckdb_optimizers`
- names the detector found: `disabled_optimizers`

```markdown
The `duckdb_optimizers()` function provides metadata about the optimization rules (e.g., `expression_rewriter`, `filter_pushdown`) available in the DuckDB instance.
These can be selectively turned off using [`PRAGMA disabled_optimizers`]({% link docs/current/configuration/pragmas.md %}#selectively-disabling-optimizers).

| Column | Description | Type |
|:-|:---|:-|
| `name` | The name of the optimization rule. | `VARCHAR` |
```

## [x] `narrative-0042`  ·  narrative-signal

- source: `sql/query_syntax/orderby.md`
- heading: ORDER BY Clause > `ORDER BY ALL` > `NULL` Order Modifier
- names the detector found: `default_null_order`, `default_order`

```markdown
By default, DuckDB sorts `ASC` and `NULLS LAST`, i.e., the values are sorted in ascending order and `NULL` values are placed last.
For the default `ASC` direction this matches PostgreSQL. Note, however, that DuckDB keeps `NULLS LAST` even for `DESC` ordering, whereas PostgreSQL places `NULL`s first on `DESC` (it treats `NULL` as the largest value). To match PostgreSQL in both directions, set `default_null_order = 'NULLS_LAST_ON_ASC_FIRST_ON_DESC'`.
The default sort order can be changed with the following configuration options.

Use the `default_null_order` option to change the default `NULL` sorting order to either `NULLS_FIRST`, `NULLS_LAST`, `NULLS_FIRST_ON_ASC_LAST_ON_DESC` or `NULLS_LAST_ON_ASC_FIRST_ON_DESC`:

```sql
SET default_null_order = 'NULLS_FIRST';
```

Use the `default_order` option to change the direction of the default sorting order to either `DESC` or `ASC`:

```sql
SET default_order = 'DESC';
```
```

## [x] `narrative-0043`  ·  narrative-signal

- source: `clients/python/data_ingestion.md`
- heading: Data Ingestion > insert into an existing table from the contents of a DataFrame > Pandas DataFrames – `object` Columns
- names the detector found: `pandas_analyze_sample`

```markdown
`pandas.DataFrame` columns of an `object` dtype require some special care, since this stores values of arbitrary type.
To convert these columns to DuckDB, we first go through an analyze phase before converting the values.
In this analyze phase a sample of all the rows of the column are analyzed to determine the target type.
This sample size is by default set to 1000.
If the type picked during the analyze step is incorrect, this will result in `Invalid Input Error: Failed to cast value`, in which case you will need to increase the sample size.
The sample size can be changed by setting the `pandas_analyze_sample` config option.

```python
```

## [x] `narrative-0045`  ·  narrative-signal

- source: `sql/statements/attach.md`
- heading: ATTACH and DETACH Statements > Examples > Name Qualification > Changing the Catalog Search Path
- names the detector found: `search_path`

```markdown
The catalog search path can be adjusted by setting the `search_path` configuration option, which uses a comma-separated list of values that will be on the search path. The following example demonstrates searching in two databases:

```sql
ATTACH ':memory:' AS db1;
ATTACH ':memory:' AS db2;
CREATE table db1.tbl1 (i INTEGER);
CREATE table db2.tbl2 (j INTEGER);
```

Reference the tables using their fully qualified name:

```sql
SELECT * FROM db1.tbl1;
SELECT * FROM db2.tbl2;
```

Or set the search path and reference the tables using their name:

```sql
SET search_path = 'db1,db2';
SELECT * FROM tbl1;
SELECT * FROM tbl2;
```
```

## [x] `narrative-0047`  ·  narrative-signal

- source: `sql/dialect/order_preservation.md`
- heading: Order Preservation > Example > Insertion Order
- names the detector found: `preserve_insertion_order`

```markdown
By default, the following components preserve insertion order:

* [CSV reader]({% link docs/current/data/csv/overview.md %}#order-preservation) (`read_csv` function)
* [JSON reader]({% link docs/current/data/json/overview.md %}#order-preservation) (`read_json` function)
* [Parquet reader]({% link docs/current/data/parquet/overview.md %}#order-preservation) (`read_parquet` function)

Preservation of insertion order is controlled by the `preserve_insertion_order` [configuration option]({% link docs/current/configuration/overview.md %}).
This setting is `true` by default, indicating that the order should be preserved.
To change this setting, use:

```sql
SET preserve_insertion_order = false;
```
```

## [x] `narrative-0051`  ·  narrative-distractor

- source: `configuration/secrets_manager.md`
- heading: Secrets Manager
- names the detector found: `username`

```markdown
The **Secrets manager** provides a unified user interface for secrets across all backends that use them. Secrets can be scoped, so different storage prefixes can have different secrets, allowing for example to join data across organizations in a single query. Secrets can also be persisted, so that they do not need to be specified every time DuckDB is launched.

> Warning Persistent secrets are stored in unencrypted binary format on the disk.
```

## [ ] `narrative-0052`  ·  narrative-distractor

- source: `sql/statements/show.md`
- heading: SHOW, SHOW DATABASES, and SHOW SCHEMAS Statements > `SHOW` Statement
- names the detector found: `schema`

```markdown
The `SHOW` statement is an alias for [`DESCRIBE`]({% link docs/current/sql/statements/describe.md %}).
It shows the schema of a table, view or query.
```

## [x] `narrative-0057`  ·  narrative-distractor

- source: `clients/wasm/data_ingestion.md`
- heading: Import Data > Overview > CSV
- names the detector found: `schema`

```markdown
Register the CSV text as a file, then load it with `insertCSVFromPath()`. The insert options describe the target table and, when auto-detection is disabled, the CSV dialect and column types:

```ts
import { Int32, Utf8 } from 'apache-arrow';

const csvContent = '1|foo\n2|bar\n';
await db.registerFileText('data.csv', csvContent);

await conn.insertCSVFromPath('data.csv', {
    schema: 'main',
    name: 'foo',
    detect: false,
    header: false,
    delimiter: '|',
    columns: {
        col1: new Int32(),
        col2: new Utf8(),
    },
});
```
```

## [x] `narrative-0058`  ·  narrative-distractor

- source: `sql/data_types/struct.md`
- heading: Struct Data Type
- names the detector found: `schema`

```markdown
Conceptually, a `STRUCT` column contains an ordered list of columns called “entries”. The entries are referenced by name using strings. This document refers to those entry names as keys. Each row in the `STRUCT` column must have the same keys. The names of the struct entries are part of the *schema*. Each row in a `STRUCT` column must have the same layout. The names of the struct entries are case-insensitive.

`STRUCT`s are typically used to nest multiple columns into a single column, and the nested column can be of any type, including other `STRUCT`s and `LIST`s.

`STRUCT`s are similar to PostgreSQL's `ROW` type. The key difference is that DuckDB `STRUCT`s require the same keys in each row of a `STRUCT` column. This allows DuckDB to provide significantly improved performance by fully utilizing its vectorized execution engine, and also enforces type consistency for improved correctness. DuckDB includes a `row` function as a special way to produce a `STRUCT`, but does not have a `ROW` data type. See an example below and the [`STRUCT` functions documentation]({% link docs/current/sql/functions/struct.md %}) for details.

See the [data types overview]({% link docs/current/sql/data_types/overview.md %}) for a comparison between nested data types.
```

## [x] `narrative-0059`  ·  narrative-distractor

- source: `sql/dialect/postgresql_compatibility.md`
- heading: PostgreSQL Compatibility > Floating-Point Arithmetic > Resolution of Type Names in the Schema
- names the detector found: `schema`

```markdown
For [`CREATE TABLE` statements]({% link docs/current/sql/statements/create_table.md %}), DuckDB attempts to resolve type names in the schema where a table is created. For example:

```sql
CREATE SCHEMA myschema;
CREATE TYPE myschema.mytype AS ENUM ('as', 'df');
CREATE TABLE myschema.mytable (v mytype);
```

PostgreSQL returns an error on the last statement:

```console
ERROR:  type "mytype" does not exist
LINE 1: CREATE TABLE myschema.mytable (v mytype);
```

DuckDB runs the statement and creates the table successfully, confirmed by the following query:

```sql
DESCRIBE myschema.mytable;
```

<div class="monospace_table"></div>

| column_name | column_type      | null | key  | default | extra |
| ----------- | ---------------- | ---- | ---- | ------- | ----- |
| v           | ENUM('as', 'df') | YES  | NULL | NULL    | NULL  |
```

## [x] `narrative-0060`  ·  narrative-distractor

- source: `sql/meta/information_schema.md`
- heading: Information Schema > Tables > `character_sets`: Character Sets
- names the detector found: `schema`

```markdown
| Column | Description | Type | Example |
|--------|-------------|------|---------|
| `character_set_catalog` | Currently not implemented – always `NULL`. | `VARCHAR` | `NULL` |
| `character_set_schema` | Currently not implemented – always `NULL`. | `VARCHAR` | `NULL` |
| `character_set_name` | Name of the character set, currently implemented as showing the name of the database encoding. | `VARCHAR` | `'UTF8'` |
| `character_repertoire` | Character repertoire, showing `UCS` if the encoding is `UTF8`, else just the encoding name. | `VARCHAR` | `'UCS'` |
| `form_of_use` | Character encoding form, same as the database encoding. | `VARCHAR` | `'UTF8'` |
| `default_collate_catalog`| Name of the database containing the default collation (always the current database). | `VARCHAR` | `'my_db'` |
| `default_collate_schema` | Name of the schema containing the default collation. | `VARCHAR` | `'pg_catalog'` |
| `default_collate_name` | Name of the default collation. | `VARCHAR` | `'ucs_basic'` |
```

