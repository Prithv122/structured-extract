This extension supports:

- Listing available tables: `SHOW ALL TABLES;`{:.language-sql .highlight}
- Interacting with tables using standard SQL: `SELECT * FROM ⟨catalog⟩.⟨schema⟩.⟨table⟩;`{:.language-sql .highlight}
- Time travel: `SELECT * FROM ... AT (VERSION => ...);`{:.language-sql .highlight}
- Inserts: `INSERT INTO ... VALUES (...);`{:.language-sql .highlight}
- Checkpointing individual tables: `CALL unity_catalog_checkpoint_table('my_catalog.my_schema.my_table');`{:.language-sql .highlight}

It does not currently support:

- `DELETE`{:.language-sql .highlight} or `UPDATE`{:.language-sql .highlight}
- Creation or manipulation of tables, views or schemas
