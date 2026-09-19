* Only vectors consisting of `FLOAT`s (32-bit, single precision) are supported at the moment.
* The index itself is not buffer managed and must be able to fit into RAM memory.
* The size of the index in memory does not count towards DuckDB's `memory_limit` configuration parameter.
* `HNSW` indexes can only be created on tables in in-memory databases, unless the `SET hnsw_enable_experimental_persistence = ⟨bool⟩`{:.language-sql .highlight} configuration option is set to `true`, see [Persistence](#persistence) for more information.
* The vector join table macros (`vss_join` and `vss_match`) do not require or make use of the `HNSW` index.
