DuckDB is able to find and query any dataframe stored as a variable in the Jupyter notebook.

```python
input_df = pd.DataFrame.from_dict({"i": [1, 2, 3],
                                   "j": ["one", "two", "three"]})
```

The dataframe being queried can be specified just like any other table in the `FROM` clause.

```sql
%sql output_df << SELECT sum(i) AS total_i FROM input_df;
```
> Warning When using the SQLAlchemy connection, make sure to run `%sql SET python_scan_all_frames=true`, to make Pandas dataframes queryable.
