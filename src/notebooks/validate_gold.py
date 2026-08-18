# Databricks notebook source
# MAGIC %md
# MAGIC # Validate Gold output
# MAGIC
# MAGIC Runs after the pipeline refresh. It confirms the Gold table:
# MAGIC
# MAGIC * **exists** in the configured catalog/schema,
# MAGIC * **has rows**, and
# MAGIC * has all **required columns**.
# MAGIC
# MAGIC If any check fails the notebook raises an exception, which fails the Job
# MAGIC task with a clear message. This is what turns a silently-empty pipeline
# MAGIC run into a loud, actionable failure.
# MAGIC
# MAGIC Catalog and schema come from notebook **widgets**, which the Job populates
# MAGIC from its `catalog` / `schema` parameters (themselves bound to bundle
# MAGIC variables). You can also run it interactively by setting the widgets.

# COMMAND ----------

# Widgets let the same notebook run under any catalog/schema without edits.
dbutils.widgets.text("catalog", "main", "Catalog")
dbutils.widgets.text("schema", "lakeflow_demo", "Schema")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

TABLE = "gold_daily_category_revenue"
FQN = f"`{catalog}`.`{schema}`.`{TABLE}`"
REQUIRED_COLUMNS = {
    "order_date",
    "product_category",
    "region",
    "order_count",
    "total_quantity",
    "total_revenue",
}

print(f"Validating {FQN}")

# COMMAND ----------

# 1) The table must exist. spark.catalog.tableExists gives a clean boolean
#    instead of an opaque AnalysisException.
if not spark.catalog.tableExists(f"{catalog}.{schema}.{TABLE}"):
    raise Exception(
        f"VALIDATION FAILED: Gold table {FQN} does not exist. "
        "The pipeline refresh may not have run, or catalog/schema is wrong."
    )

df = spark.read.table(f"{catalog}.{schema}.{TABLE}")

# COMMAND ----------

# 2) Required columns must all be present.
actual_columns = set(df.columns)
missing = REQUIRED_COLUMNS - actual_columns
if missing:
    raise Exception(
        f"VALIDATION FAILED: {FQN} is missing required column(s): "
        f"{sorted(missing)}. Found columns: {sorted(actual_columns)}."
    )

# COMMAND ----------

# 3) The table must contain at least one row.
row_count = df.count()
if row_count == 0:
    raise Exception(
        f"VALIDATION FAILED: {FQN} exists but has 0 rows. The pipeline "
        "produced no Gold output -- check the Bronze/Silver layers."
    )

# COMMAND ----------

# All checks passed. Surface a short summary for the run log.
total_revenue = df.selectExpr("sum(total_revenue) AS r").first()["r"]
print("VALIDATION PASSED")
print(f"  table          : {FQN}")
print(f"  rows           : {row_count}")
print(f"  total_revenue  : {total_revenue}")

# dbutils.notebook.exit sets the task's output value (visible in the run UI).
dbutils.notebook.exit(
    f"OK rows={row_count} total_revenue={total_revenue}"
)
