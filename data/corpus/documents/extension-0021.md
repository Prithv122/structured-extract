Originally, DuckDB extensions lived exclusively in the DuckDB main repository, `github.com/duckdb/duckdb`. These extensions are called in-tree. Later, the concept
of out-of-tree extensions was added, where extensions were separated into their own repository, which we call out-of-tree.

While from a user's perspective, there are generally no noticeable differences, there are some minor differences related to versioning:

* in-tree extensions use the version of DuckDB instead of having their own version
* in-tree extensions do not have dedicated release notes, their changes are reflected in the regular [DuckDB release notes](https://github.com/duckdb/duckdb/releases)
* core out-of tree extensions tend to live in repositories named `github.com/duckdb/duckdb-⟨extension_name⟩`{:.language-sql .highlight} but the name may vary. See the [full list]({% link docs/current/core_extensions/overview.md %}) of core extensions for details.
