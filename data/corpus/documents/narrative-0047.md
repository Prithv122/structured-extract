By default, the following components preserve insertion order:

* [CSV reader]({% link docs/current/data/csv/overview.md %}#order-preservation) (`read_csv` function)
* [JSON reader]({% link docs/current/data/json/overview.md %}#order-preservation) (`read_json` function)
* [Parquet reader]({% link docs/current/data/parquet/overview.md %}#order-preservation) (`read_parquet` function)

Preservation of insertion order is controlled by the `preserve_insertion_order` [configuration option]({% link docs/current/configuration/overview.md %}).
This setting is `true` by default, indicating that the order should be preserved.
To change this setting, use:

```sql
SET preserve_insertion_order = false;
```
