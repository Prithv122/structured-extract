Managed PostgreSQL databases running on RDS/Aurora services allow to use [IAM authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html).
In that case the authentication token is generated using AWS SDK and must be refreshed every 15 minutes.

The `postgres` extension supports IAM authentication, when the password is not specified in the secret, but instead one of the configured AWS Credential Providers is used to generate the password, that is refreshed by the `postgres` extension automatically.
