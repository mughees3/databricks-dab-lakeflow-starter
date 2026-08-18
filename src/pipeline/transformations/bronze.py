# =============================================================================
# bronze.py  --  Bronze layer: deterministic synthetic "raw" orders
# =============================================================================
# This is PIPELINE SOURCE CODE (not bundle config). It runs inside the Lakeflow
# pipeline runtime, where `spark` is provided automatically as a global.
#
# The Bronze layer generates a small, DETERMINISTIC set of synthetic retail
# order records with no external dependency -- no customer tables, no files, no
# network. Re-running the pipeline always produces the same data, which makes
# the downstream validation reproducible.
#
# Current Lakeflow Python API:
#   from pyspark import pipelines as dp   (this replaces the legacy `dlt` module)
#   @dp.materialized_view  -> batch dataset (recomputed from its inputs)
#   @dp.table              -> streaming table
# We use materialized views throughout because the data is batch-generated.
#
# Generated columns (raw, intentionally "messy" for the Silver layer to clean):
#   order_id          bigint   unique row id (0..N-1)
#   customer_id       bigint   pseudo customer (0..249)
#   product_category  string   one of 6 categories; a few rows are NULL
#   region            string   one of 4 regions
#   quantity          int      1..5; a few rows are negative (bad data)
#   unit_price_cents  int      price in cents (avoids float rounding issues)
#   order_date        date     spread across 30 days starting 2024-01-01
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql.functions import col, expr

# Number of synthetic order rows. Small enough to run in seconds on serverless.
NUM_ORDERS = 5000


@dp.materialized_view(
    comment="Bronze: raw synthetic orders, deterministically generated."
)
def bronze_orders():
    # spark.range(N) yields a deterministic column `id` from 0..N-1. Everything
    # else is a pure function of `id`, so the dataset is fully reproducible.
    return (
        spark.range(0, NUM_ORDERS)
        .withColumnRenamed("id", "order_id")
        .withColumn("customer_id", col("order_id") % 250)
        # Map id -> a category name. Every 211th row is NULL to exercise the
        # Silver cleaning step.
        .withColumn(
            "product_category",
            expr(
                "CASE WHEN order_id % 211 = 0 THEN NULL ELSE "
                "element_at(array('Electronics','Home','Apparel',"
                "'Grocery','Sports','Toys'), CAST(order_id % 6 AS INT) + 1) END"
            ),
        )
        .withColumn(
            "region",
            expr(
                "element_at(array('North','South','East','West'), "
                "CAST(order_id % 4 AS INT) + 1)"
            ),
        )
        # Every 137th row gets a negative quantity (bad data) for Silver to drop.
        .withColumn(
            "quantity",
            expr("CASE WHEN order_id % 137 = 0 THEN -1 ELSE CAST(order_id % 5 AS INT) + 1 END"),
        )
        .withColumn("unit_price_cents", (col("order_id") % 100) * 7 + 199)
        # Spread orders across 30 consecutive days.
        .withColumn(
            "order_date",
            expr("date_add(DATE'2024-01-01', CAST(order_id % 30 AS INT))"),
        )
    )
