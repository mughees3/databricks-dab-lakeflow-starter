# =============================================================================
# silver.py  --  Silver layer: cleaned & standardized orders
# =============================================================================
# Reads the Bronze table (by its unqualified dataset name -- Lakeflow resolves
# it within the pipeline's configured catalog/schema) and:
#   * drops invalid rows (NULL category, non-positive quantity or price)
#   * standardizes the category text
#   * derives a monetary `amount` as an exact DECIMAL (from integer cents)
#
# The @dp.expect_or_drop data-quality expectations document and enforce the
# cleaning rules; dropped rows are reported in the pipeline's data-quality
# metrics.
#
# Output columns:
#   order_id, customer_id, product_category, region, quantity,
#   unit_price_cents, order_date, amount (decimal(12,2))
# =============================================================================

from pyspark import pipelines as dp
from pyspark.sql.functions import col, initcap, expr


@dp.materialized_view(
    comment="Silver: cleaned and standardized orders."
)
# Expectations: rows failing these predicates are DROPPED (and counted).
@dp.expect_or_drop("valid_category", "product_category IS NOT NULL")
@dp.expect_or_drop("positive_quantity", "quantity > 0")
@dp.expect_or_drop("positive_price", "unit_price_cents > 0")
def silver_orders():
    return (
        spark.read.table("bronze_orders")
        # Standardize category capitalization (e.g. "electronics" -> "Electronics").
        .withColumn("product_category", initcap(col("product_category")))
        # amount = quantity * unit_price_cents / 100, as exact decimal money.
        .withColumn(
            "amount",
            (col("quantity") * col("unit_price_cents") / 100).cast("decimal(12,2)"),
        )
        .select(
            "order_id",
            "customer_id",
            "product_category",
            "region",
            "quantity",
            "unit_price_cents",
            "order_date",
            "amount",
        )
    )
