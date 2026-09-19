Returns the snapshots stored in the DuckLake catalog name `catalog`.

| Parameter name | Parameter type | Named parameter | Description |
| -------------- | -------------- | --------------- | ----------- |
| `catalog`      | `VARCHAR`      | no              |             |

The information is encoded into a table with the following schema:

| Column name      | Column type                |
| ---------------- | -------------------------- |
| `snapshot_id`    | `BIGINT`                   |
| `snapshot_time`  | `TIMESTAMP WITH TIME ZONE` |
| `schema_version` | `BIGINT`                   |
| `changes`        | `MAP(VARCHAR, VARCHAR[])`  |
