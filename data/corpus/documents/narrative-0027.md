A [table function]({% link docs/current/sql/query_syntax/from.md %}#table-functions) is used in place of a table in a `FROM` clause.

| Name | Description |
|:--|:-------|
| [`glob(search_path)`](#globsearch_path) | Return filenames found at the location indicated by the *search_path* in a single column named `file`. The *search_path* may contain [glob pattern matching syntax]({% link docs/current/sql/functions/pattern_matching.md %}). |
| [`repeat_row(varargs, num_rows)`](#repeat_rowvarargs-num_rows) | Returns a table with `num_rows` rows, each containing the fields defined in `varargs`. |
