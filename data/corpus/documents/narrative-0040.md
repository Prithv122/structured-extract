> Deprecated DuckDB v1.3 deprecated the old lambda single arrow syntax (`x -> x + 1`)
> in favor of the Python-style syntax (`lambda x : x + 1`).
>
> DuckDB v1.3 also introduces a new setting to configure the lambda syntax.
>
> ```sql
> SET lambda_syntax = 'DEFAULT';
> SET lambda_syntax = 'ENABLE_SINGLE_ARROW';
> SET lambda_syntax = 'DISABLE_SINGLE_ARROW';
> ```
>
> Currently, `DEFAULT` enables both syntax styles, i.e.,
> the old single arrow syntax and the Python-style syntax.
>
> DuckDB v1.5 is the last release supporting the single arrow syntax without explicitly enabling it.
>
> DuckDB v2.0 will disable the single arrow syntax by default.
>
> DuckDB v2.1 will remove the `lambda_syntax` flag and fully deprecates the single arrow syntax,
> so the old behavior will no longer be possible.
