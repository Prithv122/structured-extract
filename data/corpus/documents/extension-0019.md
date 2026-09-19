To use the `httpfs` extension with a custom certificate file, set the following [configuration options]({% link docs/current/configuration/pragmas.md %}) prior to loading the extension:

```sql
LOAD httpfs;
SET ca_cert_file = '⟨certificate_file⟩';
SET enable_server_cert_verification = true;
```

If you would like to disable SSL verification for all HTTP requests using an HTTP secret you can do so with the following statement:

```sql
CREATE SECRET disable_ssl (
    TYPE HTTP, 
    VERIFY_SSL 0
);
```

To enable it again for one specific endpoint, you can take advantage of the scope parameter:

```sql
CREATE SECRET enable_ssl_for_your_website (
    TYPE HTTP, 
    SCOPE 'https://⟨your-website.com⟩', 
    VERIFY_SSL 1
); 
```
