Authentication from the `postgres` extension uses the same logic as with `psql`:

* The secret of type `rds` is used to generate the authentication token, it takes the same configuration parameters as the `aws rds generate-db-auth-token` command in the example above:

  ```sql
  CREATE SECRET aws_rds_secret1 (
      TYPE rds,
      PROVIDER credential_chain,
      CHAIN 'env;sso;',
      REGION 'eu-west-1',
      RDS_USER 'postgres',
      RDS_HOST 'database-1-instance-1.xxxxxxxxxxxx.eu-west-1.rds.amazonaws.com',
      RDS_PORT '5432'
  );
  ```

* The secret of type `postgres` is used to create the remaining of the connection string. It takes the same parameters as the `psql` utility in the example above (and additionally any relevant additional `libpq` configuration options) and requires to specify the name of the `rds` secret, that is used to generate and periodically refresh (automatically) the authentication token that is passed to server as a `password`:

  ```sql
  CREATE SECRET pg_rds_secret1 (
      TYPE postgres,
      HOST 'database-1-instance-1.xxxxxxxxxxxx.eu-west-1.rds.amazonaws.com',
      PORT '5432',
      USER 'postgres',
      DATABASE 'postgres',
      SSLMODE require,
      AWS_RDS_SECRET aws_rds_secret1
  );
  ```

The secret of type `rds` requires the `aws` extension to be installed and allows to configure AWS Credential Chain the same way as with the secret of type `s3`, see details in the [AWS extension documentation]({% link docs/current/core_extensions/aws.md %}#credential_chain-provider).
