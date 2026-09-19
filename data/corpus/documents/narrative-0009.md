When the `PARTITION_BY` clause is specified for the [`COPY` statement]({% link docs/current/sql/statements/copy.md %}), the files are written in a [Hive partitioned]({% link docs/current/data/partitioning/hive_partitioning.md %}) folder hierarchy. The target is the name of the root directory (in the example above: `orders`). The files are written in-order in the file hierarchy. Currently, one file is written per thread to each directory.

```text
orders
├── year=2021
│    ├── month=1
│    │   ├── data_1.parquet
│    │   └── data_2.parquet
│    └── month=2
│        └── data_1.parquet
└── year=2022
     ├── month=11
     │   ├── data_1.parquet
     │   └── data_2.parquet
     └── month=12
         └── data_1.parquet
```

The values of the partitions are automatically extracted from the data. Note that it can be very expensive to write a larger number of partitions as many files will be created. The ideal partition count depends on how large your dataset is.

To limit the maximum number of files the system can keep open before flushing to disk when writing using `PARTITION_BY`, use the `partitioned_write_max_open_files` configuration option (default: 100):

```batch
SET partitioned_write_max_open_files = 10;
```

> Bestpractice Writing data into many small partitions is expensive. It is generally recommended to have at least `100 MB` of data per partition.
