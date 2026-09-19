| Column | Description | Type | Example |
|--------|-------------|------|---------|
| `character_set_catalog` | Currently not implemented – always `NULL`. | `VARCHAR` | `NULL` |
| `character_set_schema` | Currently not implemented – always `NULL`. | `VARCHAR` | `NULL` |
| `character_set_name` | Name of the character set, currently implemented as showing the name of the database encoding. | `VARCHAR` | `'UTF8'` |
| `character_repertoire` | Character repertoire, showing `UCS` if the encoding is `UTF8`, else just the encoding name. | `VARCHAR` | `'UCS'` |
| `form_of_use` | Character encoding form, same as the database encoding. | `VARCHAR` | `'UTF8'` |
| `default_collate_catalog`| Name of the database containing the default collation (always the current database). | `VARCHAR` | `'my_db'` |
| `default_collate_schema` | Name of the schema containing the default collation. | `VARCHAR` | `'pg_catalog'` |
| `default_collate_name` | Name of the default collation. | `VARCHAR` | `'ucs_basic'` |
