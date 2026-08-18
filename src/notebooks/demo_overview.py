# Databricks notebook source
# MAGIC %md
# MAGIC # Lakeflow demo -- Gold overview
# MAGIC
# MAGIC A short, **read-only** walkthrough of the Gold table for a customer demo.
# MAGIC It never writes or modifies data, so it is safe to run repeatedly. The Job
# MAGIC runs it as an optional final step; you can also open it interactively.
# MAGIC
# MAGIC Catalog/schema come from widgets (populated by the Job parameters).

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Catalog")
dbutils.widgets.text("schema", "lakeflow_demo", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# Set the active catalog/schema so unqualified table names resolve.
spark.sql(f"USE CATALOG `{catalog}`")
spark.sql(f"USE SCHEMA `{schema}`")
print(f"Reading from `{catalog}`.`{schema}`")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Headline metric: total revenue and orders

# COMMAND ----------

display(
    spark.sql(
        """
        SELECT
          SUM(total_revenue) AS total_revenue,
          SUM(order_count)   AS total_orders,
          SUM(total_quantity) AS total_units
        FROM gold_daily_category_revenue
        """
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Revenue by product category

# COMMAND ----------

display(
    spark.sql(
        """
        SELECT product_category, SUM(total_revenue) AS revenue
        FROM gold_daily_category_revenue
        GROUP BY product_category
        ORDER BY revenue DESC
        """
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Daily revenue trend

# COMMAND ----------

display(
    spark.sql(
        """
        SELECT order_date, SUM(total_revenue) AS revenue
        FROM gold_daily_category_revenue
        GROUP BY order_date
        ORDER BY order_date
        """
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC The same Gold table backs the AI/BI dashboard deployed by this bundle
# MAGIC (`Lakeflow Demo -- Gold Metrics`). See `docs/customization.md` to change
# MAGIC these queries or add visualizations.
