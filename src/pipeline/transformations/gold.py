# =============================================================================
# gold.py  --  Gold layer: business-ready aggregated metric
# =============================================================================
# Reads the Silver table and aggregates a useful business metric: daily revenue
# broken down by product category and region. This single Gold table supports
# every dashboard view (a total-revenue summary, a by-category comparison, and
# a day-over-day trend).
#
# Output table: gold_daily_category_revenue
#   order_date        date      the order day
#   product_category  string    product category
#   region            string    sales region
#   order_count       bigint    number of orders in that (day, category, region)
#   total_quantity    bigint    units sold
#   total_revenue     decimal   revenue (sum of Silver `amount`)
#
# This is the table the Job's validate_gold notebook checks and the AI/BI
# dashboard reads.
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql.functions import col, count, sum as _sum


@dp.materialized_view(
    comment="Gold: daily revenue by category and region."
)
def gold_daily_category_revenue():
    return (
        spark.read.table("silver_orders")
        .groupBy("order_date", "product_category", "region")
        .agg(
            count("order_id").alias("order_count"),
            _sum("quantity").alias("total_quantity"),
            _sum("amount").alias("total_revenue"),
        )
        .orderBy("order_date", "product_category", "region")
    )
