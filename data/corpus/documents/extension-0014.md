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
