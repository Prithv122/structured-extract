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
