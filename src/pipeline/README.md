# Pipeline source

This folder holds the **source code** for the Lakeflow Spark Declarative
Pipeline. It is deliberately separate from the bundle **configuration** in
`resources/pipeline.yml`:

| Concern | Lives in | Example |
| --- | --- | --- |
| *How* the pipeline is created & run | `resources/pipeline.yml` | serverless, catalog/schema, channel |
| *What* the pipeline computes | `src/pipeline/transformations/*.py` | Bronze/Silver/Gold logic |

## Transformations

The pipeline is a classic medallion flow. Each file defines one layer:

| File | Dataset | Type | What it does |
| --- | --- | --- | --- |
| `transformations/bronze.py` | `bronze_orders` | materialized view | Generates 5,000 deterministic synthetic order rows (some intentionally "dirty"). |
| `transformations/silver.py` | `silver_orders` | materialized view | Drops invalid rows, standardizes text, computes an exact-decimal `amount`. |
| `transformations/gold.py` | `gold_daily_category_revenue` | materialized view | Aggregates daily revenue by category and region. |

The `resources/pipeline.yml` glob (`transformations/**`) auto-includes every
file here, so adding a new transformation file is enough to add it to the
pipeline.

## API used

These modules use the **current** Lakeflow Python API:

```python
from pyspark import pipelines as dp   # replaces the legacy `dlt` module

@dp.materialized_view   # batch dataset
@dp.table               # streaming table
@dp.expect_or_drop(...) # data-quality expectation
```

`spark` is provided automatically by the pipeline runtime — do not create a
`SparkSession` yourself. Reads of other datasets in the same pipeline use the
**unqualified** table name (`spark.read.table("bronze_orders")`); Lakeflow
resolves them within the pipeline's configured catalog/schema.

> The legacy `import dlt` / `@dlt.table` API still works, but Databricks
> recommends `pyspark.pipelines` for new code.

## Expected output

After a successful refresh you will find three tables in the configured
`${catalog}`.`${schema}`:

- `bronze_orders` — ~5,000 rows
- `silver_orders` — slightly fewer (dirty rows dropped)
- `gold_daily_category_revenue` — one row per (day, category, region)
