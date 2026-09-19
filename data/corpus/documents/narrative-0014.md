The `GEOMETRY` type supports a storage optimization called "shredding", which improves compression for geometry columns where all values share the same geometry type and vertex dimensions.

When a row group qualifies, DuckDB splits the geometry segment within the row group into primitive `STRUCT`, `LIST`, and `DOUBLE` segments that can be compressed independently using lightweight algorithms - far more efficiently than storing variable-size binary blobs.

The shredded layout depends on the geometry type:

- `POINT` - STRUCT(X DOUBLE, Y DOUBLE) (and/or Z, M)
- `LINESTRING` - STRUCT(X DOUBLE, Y DOUBLE)[]
- `POLYGON` - STRUCT(X DOUBLE, Y DOUBLE)[][]
- `MULTIPOINT`, `MULTILINESTRING`, `MULTIPOLYGON` - same as above, with one additional level of list nesting
 
Row groups are not shredded if they contain `GEOMETRYCOLLECTION`s, any `EMPTY` geometries, or multiple geometry sub-types.

Additionally, row groups are not shredded if they fall below the minimum size threshold (default: ~25% of the maximum row group size, i.e., 30,000 rows).

This threshold is configurable via the `geometry_minimum_shredding_size` setting. Set it to `0` to always shred, or `-1` to disable shredding entirely.

```sql
-- Disable shredding for geometry columns
SET geometry_minimum_shredding_size = -1;

-- Always shred geometry columns regardless of row group size
SET geometry_minimum_shredding_size = 0;
```

The primary benefit of shredding is significantly improved compression, but in the future we plan to add ways to expose the shredded representation directly to the execution engine without having to "reassemble" the geometry back into binary again.

The following example illustrates the effects of shredding on the storage footprint of a `GEOMETRY` column.

```sql
-- Attach a persistent database with storage version v1.5
ATTACH 'geometry_db.db' as geometry_db (STORAGE_VERSION 'v1.5.0');

USE geometry_db;

-- Disable shredding completely and create a table with 1 million 2D points
SET geometry_minimum_shredding_size = -1;

CREATE OR REPLACE TABLE points AS SELECT printf('POINT (%d %d)', x, y)::GEOMETRY AS geom 
FROM range(0, 1000) AS rx(x), range(0, 1000) AS ry(y);

-- Checkpoint the database to persist the data and storage layout to disk
CHECKPOINT;

-- Attach a second database
ATTACH 'shredded_db.db' as shredded_db (STORAGE_VERSION 'v1.5.0');

USE shredded_db;

-- This time, set the minimum shredding size to 0 to always shred geometry columns,
-- and create the same table with 1 million 2D points
SET geometry_minimum_shredding_size = 0;

CREATE OR REPLACE TABLE points AS SELECT printf('POINT (%d %d)', x, y)::GEOMETRY AS geom 
FROM range(0, 1000) AS rx(x), range(0, 1000) AS ry(y);

-- Checkpoint to persist the data and storage layout to disk, and apply shredding
CHECKPOINT;

-- Now check the storage layout and memory usage of the geometry column in both attached databases
SELECT database_name, database_size FROM pragma_database_size();
----
┌───────────────┬───────────────┐
│ database_name │ database_size │
│    varchar    │    varchar    │
├───────────────┼───────────────┤
│ shredded_db   │ 2.2 MiB       │ -- Almost 3x smaller storage thanks to shredding!
│ geometry_db   │ 6.5 MiB       │ 
│ memory        │ 0 bytes       │
└───────────────┴───────────────┘

-- We can inspect what type of segments are used to store the geometry column 
-- in each database using the `pragma_storage_info` function. 

-- The geometry column in `geometry_db` is stored as regular GEOMETRY segments
SELECT DISTINCT(segment_type) FROM pragma_storage_info('geometry_db.points');
----
┌──────────────┐
│ segment_type │
│   varchar    │
├──────────────┤
│ GEOMETRY     │
│ VALIDITY     │
└──────────────┘

-- While the geometry column in `shredded_db` is decomposed into primitive DOUBLE segments,
-- which can be compressed much more efficiently!
SELECT DISTINCT(segment_type) FROM pragma_storage_info('shredded_db.points');
----
┌──────────────┐
│ segment_type │
│   varchar    │
├──────────────┤
│ VALIDITY     │
│ DOUBLE       │
└──────────────┘
```
