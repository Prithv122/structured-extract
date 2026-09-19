The CSV reader respects the `preserve_insertion_order` [configuration option]({% link docs/current/configuration/overview.md %}) to [preserve insertion order]({% link docs/current/sql/dialect/order_preservation.md %}).
When `true` (the default), the order of the rows in the result set returned by the CSV reader is the same as the order of the corresponding lines read from the file(s).
When `false`, there is no guarantee that the order is preserved.
