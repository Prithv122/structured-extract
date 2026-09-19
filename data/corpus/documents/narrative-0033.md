```php
<?php

$db = new PDO('duckdb::memory:'); // open in-memory database

$db = new PDO('duckdb:/tmp/test.db'); // open database file from disk

// open database file as read-only
$db = new PDO('duckdb:/tmp/test.db', null, null, [PDO::DUCKDB_ATTR_CONFIG => ['access_mode' => 'read_only']]);
```
