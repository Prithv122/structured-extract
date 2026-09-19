DuckDB supports HTTP proxies.

You can add an HTTP proxy using the [Secrets Manager]({% link docs/current/configuration/secrets_manager.md %}):

```sql
CREATE SECRET http_proxy (
    TYPE http,
    HTTP_PROXY '⟨http_proxy_url⟩',
    HTTP_PROXY_USERNAME '⟨username⟩',
    HTTP_PROXY_PASSWORD '⟨password⟩'
);
```

You can also set the scope for an HTTP proxy using the `SCOPE` keyword.

```sql
CREATE SECRET http_proxy (
    TYPE HTTP, 
    SCOPE ['⟨https://duckdb.org⟩', '⟨https://some-other-website.org⟩'], 
    HTTP_PROXY '⟨http_proxy_url⟩',
    HTTP_PROXY_USERNAME '⟨username⟩',
    HTTP_PROXY_PASSWORD '⟨password⟩'
);
```

Alternatively, you can add it via [configuration options]({% link docs/current/configuration/pragmas.md %}):

```sql
SET http_proxy = '⟨http_proxy_url⟩';
SET http_proxy_username = '⟨username⟩';
SET http_proxy_password = '⟨password⟩';
```

Note: You cannot set a proxy scope using the configurations options.
