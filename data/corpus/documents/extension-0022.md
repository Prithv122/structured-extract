[Iceberg table properties](https://iceberg.apache.org/spec/#table-metadata-fields) can be set at creation time with a `WITH` clause. The `format-version` and `location` keys are recognized specially; any other key-value pairs are stored as table properties:

```sql
CREATE TABLE my_catalog.sales.events (a INTEGER)
WITH (
    'format-version' = '2',                 -- Iceberg format version (2 or 3)
    'location' = 's3://my-bucket/events',   -- base location for the table's data
    'my.custom.property' = 'value'
);
```

Existing properties can be inspected and modified with the property functions:

```sql
-- View properties
SELECT * FROM iceberg_table_properties(my_catalog.sales.events);

-- Set properties
CALL set_iceberg_table_properties(
    my_catalog.sales.events,
    MAP {'write.update.mode': 'merge-on-read', 'write.delete.mode': 'merge-on-read'}
);

-- Remove properties
CALL remove_iceberg_table_properties(my_catalog.sales.events, ['my.custom.property']);
```

See the [Functions and Settings Reference]({% link docs/current/core_extensions/iceberg/reference.md %}#table-and-schema-property-functions) for the equivalent schema (namespace) property functions.
