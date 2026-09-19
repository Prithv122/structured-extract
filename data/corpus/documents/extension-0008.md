By default, jemalloc's [background threads](https://jemalloc.net/jemalloc.3.html#background_thread) are disabled. To enable them, use the following configuration option:

```sql
SET allocator_background_threads = true;
```

Background threads asynchronously purge outstanding allocations so that this doesn't have to be done synchronously by the foreground threads. This improves allocation performance, and should be noticeable in allocation-heavy workloads, especially on many-core CPUs.
