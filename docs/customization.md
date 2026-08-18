# Customization

How to adapt each part of the sample. Line/anchor references are to files in
this repo. After any change, run `databricks bundle validate -t dev` (or
`scripts/validate.sh`).

## Replace synthetic data with customer data

The synthetic generator is `src/pipeline/transformations/bronze.py`. Replace the
body of `bronze_orders()` with a real source, keeping the same output columns
(or update Silver/Gold accordingly):

```python
from pyspark import pipelines as dp

@dp.materialized_view          # batch source
def bronze_orders():
    return spark.read.table("my_catalog.raw.orders")

# For a streaming/incremental source, use a streaming table instead:
@dp.table
def bronze_orders():
    return (spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .load("/Volumes/my_catalog/raw/orders/"))
```

`spark` is provided by the runtime — do not create a `SparkSession`. Read other
pipeline datasets by their **unqualified** name (`spark.read.table("bronze_orders")`).

## Add a new pipeline transformation

Create a new file under `src/pipeline/transformations/` (e.g. `platinum.py`).
The glob in `resources/pipeline.yml` (`transformations/**`) picks it up
automatically — no config change needed.

```python
from pyspark import pipelines as dp
from pyspark.sql.functions import col

@dp.materialized_view
def top_categories():
    return (spark.read.table("gold_daily_category_revenue")
        .groupBy("product_category")
        .sum("total_revenue"))
```

## Add another Job task

Edit `resources/job.yml` and add to `tasks:`. Use `depends_on` to order it:

```yaml
        - task_key: my_new_task
          depends_on:
            - task_key: validate_gold
          notebook_task:
            notebook_path: ../src/notebooks/my_notebook.py
            base_parameters:
              catalog: ${var.catalog}
              schema: ${var.schema}
```

## Add or replace a notebook

Notebook **source** files here are Databricks-format `.py` files: the first
line is `# Databricks notebook source`, cells are separated by
`# COMMAND ----------`, and Markdown cells use `# MAGIC %md`. When deployed they
become workspace **notebooks** (the `.py` extension is dropped automatically),
which is why the Job references them as `../src/notebooks/<name>.py`.

**Prefer `.ipynb`?** Just drop an `.ipynb` file in `src/notebooks/` and point
`notebook_path` at it (with the `.ipynb` extension). Both formats are supported;
`.py` is friendlier to code review and diffs.

Pass parameters via `base_parameters` (read in the notebook with
`dbutils.widgets.get("name")`), as `validate_gold.py` does.

## Add or modify a dashboard visualization

The dashboard is `src/dashboards/lakeflow_demo.lvdash.json`. Two workflows:

- **Edit in the UI, then export:** open the deployed dashboard, change queries
  or widgets, then *File → Export* (or pull the definition with the CLI) and
  save the JSON back over this file. This is the most reliable way to get
  correct widget specs.
- **Edit the JSON directly:** add a dataset under `datasets` (with `queryLines`)
  and a widget under `pages[].layout` referencing that dataset. Widget `spec`
  fields must match the AI/BI schema — copy an existing widget as a template.

**Catalog/schema in dashboard queries:** the bundle does **not** substitute
`${var.*}` inside the `.lvdash.json` file, so its dataset SQL uses a fixed
`main.lakeflow_demo`. If your target schema differs (dev is per-user by
default), either (a) edit the two table references in the JSON, (b) set your
dev/prod schema to `lakeflow_demo`, or (c) repoint the datasets in the UI after
deploy.

## Add a second environment

Add another target under `targets:` in `databricks.yml`, e.g. `staging`:

```yaml
  staging:
    mode: production
    workspace:
      root_path: /Workspace/Users/CHANGE_ME_PRINCIPAL/.bundle/${bundle.name}/${bundle.target}
    variables:
      catalog: main
      schema: lakeflow_demo_staging
```

Select it with `-t staging`.

## Change compute settings

**Pipeline** (`resources/pipeline.yml`) — to use classic compute instead of
serverless, set `serverless: false` and add a cluster:

```yaml
      serverless: false
      clusters:
        - label: default
          num_workers: 2
          node_type_id: m5d.large     # an AWS instance type available in your workspace
```

**Job notebook tasks** (`resources/job.yml`) — to pin a job cluster instead of
serverless, add a `job_clusters` block and reference it per task:

```yaml
      job_clusters:
        - job_cluster_key: main
          new_cluster:
            spark_version: 15.4.x-scala2.12
            num_workers: 1
            node_type_id: m5d.large
      tasks:
        - task_key: validate_gold
          job_cluster_key: main
          notebook_task: { ... }
```

## Add secrets safely

Never put secrets in the bundle. Use Databricks **secret scopes**:

```bash
databricks secrets create-scope my_scope
databricks secrets put-secret my_scope my_key
```

Reference them at runtime, e.g. in a notebook
`dbutils.secrets.get("my_scope", "my_key")`, or in a resource field as
`{{secrets/my_scope/my_key}}` where supported. You can also declare a
`secret_scopes` resource in the bundle (see the bundle schema) to manage scopes
as code — but store the secret *values* out of band, not in Git.

## Add permissions and a production run identity

In `databricks.yml`'s `prod` target (search for `CHANGE_ME`):

```yaml
    run_as:
      service_principal_name: <app-id-of-your-service-principal>
    permissions:
      - service_principal_name: <app-id>
        level: CAN_MANAGE
      - group_name: data-platform-admins
        level: CAN_MANAGE
```

A **service principal** is strongly recommended for prod so deployments do not
depend on any individual's account.

## Keep environment-specific values out of source code

- Use **variables** (`${var.catalog}`, `${var.schema}`, …) in resource YAML and
  pass values per target or with `--var key=value`.
- Use **notebook widgets** / **job parameters** for anything the code needs at
  runtime — never hardcode a catalog, schema, warehouse, or path in `src/`.
- Use `${workspace.current_user.short_name}`, `${bundle.target}`, and
  `${resources.<type>.<key>.id}` substitutions instead of literals.
