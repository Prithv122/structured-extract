```sql
SET variable_name = variable_value;
```

Where `variable_name` can be one of the following:

| Name | Description | Type | Default |
|:---|:---|:---|:---|
| `azure_storage_connection_string` | Azure connection string, used for authenticating and configuring Azure requests. | `STRING` | - |
| `azure_account_name` | Azure account name, when set, the extension will attempt to automatically detect credentials (not used if you pass the connection string). | `STRING` | - |
| `azure_endpoint` | Override the Azure endpoint for when the Azure credential providers are used. | `STRING` | `blob.core.windows.net` |
| `azure_credential_chain`| Ordered list of Azure credential providers, in string format separated by `;`. For example: `'cli;managed_identity;env'`. See the list of possible values in the [`credential_chain` provider section](#credential_chain-provider). Not used if you pass the connection string. | `STRING` | - |
| `azure_http_proxy` | Proxy to use when login & performing request to Azure. | `STRING` | `HTTP_PROXY` environment variable (if set). |
| `azure_proxy_user_name` | HTTP proxy username if needed. | `STRING` | - |
| `azure_proxy_password` | HTTP proxy password if needed. | `STRING` | - |
