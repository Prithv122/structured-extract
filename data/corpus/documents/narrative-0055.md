You might be piping data through `jq` or downloading a JSON file from somewhere. You can also tell DuckDB to read data from another process by changing the filename to `/dev/stdin`.

Let's combine this with a quick `curl` from GitHub to see what a certain user has been up to lately.

```batch
curl -sL "https://api.github.com/users/dacort/events?per_page=100" \
     | duckdb -s "COPY (SELECT type, count(*) AS event_count FROM read_json('/dev/stdin') GROUP BY 1 ORDER BY 2 DESC LIMIT 10) TO '/dev/stdout' WITH (FORMAT csv, HEADER)" \
     | uplot bar -d, -H -t "GitHub Events for @dacort"
```

![github-events](/images/guides/youplot/github-events.png)
