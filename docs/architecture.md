# Architecture

## Flow: from local Git to a running workload

```
Local Git repository
        |
        v
Databricks CLI bundle validation      (databricks bundle validate -t <target>)
        |
        v
DAB deployment to target workspace     (databricks bundle deploy -t <target>)
        |
        +--> Lakeflow Pipeline: Bronze -> Silver -> Gold
        |
        +--> Lakeflow Job: refresh pipeline -> validate Gold output -> (overview)
        |
        +--> AI/BI Dashboard: reads the Gold table
```

1. **Author** configuration (`databricks.yml`, `resources/*.yml`) and code
   (`src/**`) in Git.
2. **Validate** — the CLI parses the YAML, resolves variables and
   substitutions, and checks everything against the current bundle schema.
3. **Deploy** — the CLI uploads the source files to the target's workspace path
   and creates/updates the pipeline, job, and dashboard.
4. **Run** — the Job refreshes the pipeline (Bronze→Silver→Gold), then runs the
   validation notebook against the Gold table.

## The medallion pipeline

| Layer | Dataset | Source | Purpose |
| --- | --- | --- | --- |
| Bronze | `bronze_orders` | `spark.range` (synthetic) | Deterministic raw orders, incl. a few intentionally "dirty" rows |
| Silver | `silver_orders` | reads `bronze_orders` | Drop invalid rows, standardize, compute exact-decimal `amount` |
| Gold | `gold_daily_category_revenue` | reads `silver_orders` | Aggregate daily revenue by category and region |

The Job's `validate_gold` task then reads the Gold table and fails the run if
it is missing, empty, or missing required columns.

## What is source-controlled vs target-specific vs created remotely

**Source-controlled (in this repo, identical for every environment):**

- `databricks.yml` — bundle identity, includes, variable *declarations*, targets.
- `resources/*.yml` — pipeline, job, and dashboard *definitions*.
- `src/**` — pipeline transformation code, notebooks, dashboard JSON.
- `tests/`, `scripts/`, `docs/`.

**Target-specific (differs between dev and prod, set in `databricks.yml`
`targets:`):**

- Variable *values*: `catalog`, `schema`, `warehouse_id`, `pipeline_channel`.
- `mode` — `development` (dev) vs `production` (prod).
- The workspace deployment-state `root_path`.
- `run_as` identity and `permissions` (prod).

**Created remotely at deploy time (in the workspace, not in Git):**

- Uploaded copies of `src/**` under the target's `root_path/files/…`.
- The pipeline, job, and dashboard objects.
- The pipeline's managed **tables** (Bronze/Silver/Gold) in Unity Catalog when
  the pipeline runs.
- Bundle deployment **state** (what the bundle currently manages), stored under
  the target's `root_path`.

## Dev vs prod isolation

- **dev** uses `mode: development`: resource names get a `[dev <user>]` prefix,
  the schema is per-user (`<user>_lakeflow_demo`), schedules/triggers are
  paused, and each user's deployment state lives under their own
  `/Workspace/Users/<user>/.bundle/…`. Multiple engineers can deploy the same
  bundle without colliding.
- **prod** uses `mode: production`: no name prefixing, a fixed shared schema, a
  single deterministic `root_path` (never `/Shared`), an explicit `run_as`
  identity, and explicit `permissions`.

## Compute

Both the pipeline and the Job's notebook tasks use **serverless** compute by
default — the simplest and cheapest option for a new workspace, with nothing to
size or keep warm. Compute is configurable; see `docs/customization.md` to
switch to classic clusters.
