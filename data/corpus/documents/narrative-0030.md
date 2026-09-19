Values of a particular data type cannot always be cast to any arbitrary target data type. The only exception is the `NULL` value – which can always be converted between types.
The following matrix describes which conversions are supported.
When implicit casting is allowed, it implies that explicit casting is also possible.

![Typecasting matrix](/images/typecasting-matrix.png)

Even though a casting operation is supported based on the source and target data type, it does not necessarily mean the cast operation will succeed at runtime.

> Deprecated Prior to version 0.10.0, DuckDB allowed any type to be implicitly cast to `VARCHAR` during function binding.
> Version 0.10.0 introduced a [breaking change which no longer allows implicit casts to `VARCHAR`]({% post_url 2024-02-13-announcing-duckdb-0100 %}#breaking-sql-changes).
> The [`old_implicit_casting` configuration option]({% link docs/current/configuration/pragmas.md %}#implicit-casting-to-varchar) setting can be used to revert to the old behavior.
> However, please note that this flag will be deprecated in the future.
