Use the following [configuration options]({% link docs/current/configuration/overview.md %}) to control how the extension reads remote files:

| Name | Description | Type | Default |
|:---|:---|:---|:---|
| `azure_http_stats` | Include HTTP info from Azure Storage in the [`EXPLAIN ANALYZE` statement]({% link docs/current/dev/profiling.md %}). | `BOOLEAN` | `false` |
| `azure_read_transfer_concurrency` | Maximum number of threads the Azure client can use for a single parallel read. If `azure_read_transfer_chunk_size` is less than `azure_read_buffer_size` then setting this > 1 will allow the Azure client to do concurrent requests to fill the buffer. | `BIGINT` | `5` |
| `azure_read_transfer_chunk_size` | Maximum size in bytes that the Azure client will read in a single request. It is recommended that this is a factor of `azure_read_buffer_size`. | `BIGINT` | `1024*1024` |
| `azure_read_buffer_size` | Size of the read buffer. It is recommended that this is evenly divisible by `azure_read_transfer_chunk_size`. | `UBIGINT` | `1024*1024` |
| `azure_transport_option_type` | Underlying [adapter](https://github.com/Azure/azure-sdk-for-cpp/blob/main/doc/HttpTransportAdapter.md) to use in the Azure SDK. Valid values are: `default` or `curl`. | `VARCHAR` | `default` |
| `azure_context_caching` | Enable/disable the caching of the underlying Azure SDK HTTP connection in the DuckDB connection context when performing queries. If you suspect that this is causing some side effect, you can try to disable it by setting it to false (not recommended). | `BOOLEAN` | `true` |

> Setting `azure_transport_option_type` explicitly to `curl` will have the following effect:
> * On Linux, this may solve certificate issue (`Error: Invalid Error: Fail to get a new connection for: https://storage_account_name.blob.core.windows.net/. Problem with the SSL CA cert (path? access rights?)`) because when specifying the extension will try to find the bundle certificate in various paths (that is not done by *curl* by default and might be wrong due to static linking).
> * On Windows, this replaces the default adapter (*WinHTTP*) allowing you to use all *curl* capabilities (for example using a socks proxies).
> * On all operating systems, it will honor the following environment variables:
>   * `CURL_CA_INFO`: Path to a PEM encoded file containing the certificate authorities sent to libcurl. Note that this option is known to only work on Linux and might throw if set on other platforms.
>   * `CURL_CA_PATH`: Path to a directory which holds PEM encoded files, containing the certificate authorities sent to libcurl.

Example:

```sql
SET azure_http_stats = false;
SET azure_read_transfer_concurrency = 5;
SET azure_read_transfer_chunk_size = 1_048_576;
SET azure_read_buffer_size = 1_048_576;
```
