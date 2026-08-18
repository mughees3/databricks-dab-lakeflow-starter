# AWS Databricks DAB starter — Lakeflow pipeline + Job + AI/BI dashboard

A minimal, working, source-controlled example of a **Declarative Automation
Bundle (DAB)** — commonly still called a **Databricks Asset Bundle** — on **AWS
Databricks**. Clone it, point it at your workspace, and deploy a complete
medallion workload with the local Databricks CLI.

> **This sample is illustrative.** It is intentionally small and safe. Review
> every resource, permission, and compute choice before using anything like it
> in production.

---

## What are DABs?

A DAB packages your Databricks resources — pipelines, jobs, dashboards, and
more — as **YAML configuration plus source code in Git**. The Databricks CLI
reads the bundle and creates/updates those resources in a workspace. You get
repeatable deployments, per-environment configuration (dev vs prod), and code
review for infrastructure — without writing Terraform.

## What this bundle deploys

| Resource | Key | What it is |
| --- | --- | --- |
| Lakeflow Spark Declarative Pipeline | `lakeflow_demo_pipeline` | Bronze → Silver → Gold medallion flow over deterministic synthetic data |
| Lakeflow Job | `lakeflow_demo_job` | Refreshes the pipeline, then validates the Gold output, then runs a read-only overview notebook |
| AI/BI dashboard | `lakeflow_demo_dashboard` | Total-revenue counter, revenue-by-category bar, daily-revenue trend line |

Everything runs on **serverless** compute by default and uses only
**synthetic data generated inside the pipeline** — no customer data, no
external sources.

## Repository structure

```
aws-dab-lakeflow-starter/
├── databricks.yml              # Bundle entry point: name, includes, variables, targets
├── resources/                  # One resource definition per file
│   ├── pipeline.yml            #   Lakeflow pipeline (serverless, catalog/schema)
│   ├── job.yml                 #   Job: refresh pipeline → validate Gold → overview
│   └── dashboard.yml           #   AI/BI dashboard on the Gold table
├── src/
│   ├── pipeline/transformations/   # Pipeline SOURCE CODE (medallion layers)
│   │   ├── bronze.py           #   synthetic raw orders
│   │   ├── silver.py           #   cleaned/standardized orders
│   │   └── gold.py             #   daily revenue by category & region
│   ├── notebooks/
│   │   ├── validate_gold.py    #   post-refresh validation (fails loudly)
│   │   └── demo_overview.py    #   read-only walkthrough
│   └── dashboards/
│       └── lakeflow_demo.lvdash.json   # serialized AI/BI dashboard
├── tests/                      # Offline static checks (no workspace needed)
├── scripts/                    # validate / deploy / run / destroy wrappers
└── docs/                       # architecture, customization, troubleshooting, test plan, CI/CD
```

**Separation of concerns:** *configuration* lives in `databricks.yml` +
`resources/`; *code* lives in `src/`. You can change compute or the target
schema without touching transformation logic, and vice-versa.

## Prerequisites

- **Databricks CLI** v0.218+ (this repo was verified with **v1.0.0**). Install:
  <https://docs.databricks.com/aws/en/dev-tools/cli/install>. Check with
  `databricks version`.
- An **AWS Databricks workspace with Unity Catalog** enabled.
- **Serverless** compute enabled (for the default compute path), or read
  `docs/customization.md` to switch to classic clusters.
- Permission to create schemas/tables in a catalog (default `main`), create
  jobs and pipelines, and create dashboards. A **SQL warehouse** is needed to
  view the dashboard.
- Python 3.9+ only if you want to run the local `tests/` (optional).

## Authentication (no secrets in the repo)

Authenticate the CLI once, interactively (OAuth U2M):

```bash
databricks auth login --host https://<your-workspace>.cloud.databricks.com
```

This bundle does **not** hardcode a workspace URL. The CLI resolves the host
from, in order: `-p <profile>`, the `DATABRICKS_HOST` environment variable, or a
`workspace.host:` you add to a target in `databricks.yml`. Confirm auth with:

```bash
databricks current-user me
```

For automation, use a **service principal** with OAuth (M2M) or OIDC — see
`docs/ci-cd-integration.md`. Never commit tokens.

## Configure catalog and schema

Defaults live in `databricks.yml` under `variables:` and are assigned per
target:

- **dev** (default): `catalog=main`, `schema=<your_name>_lakeflow_demo`
  (per-user, so engineers never collide).
- **prod**: `catalog=main`, `schema=lakeflow_demo_prod` (fixed, shared).

Override without editing files:

```bash
databricks bundle deploy -t dev --var catalog=my_catalog --var schema=my_schema
```

The **dashboard** query text can't be templated by the bundle, so its shipped
SQL points at `main.lakeflow_demo`. If your dev schema differs, see
`docs/customization.md` → *Modify a dashboard*.

## The local workflow

From the repo root (scripts wrap the raw CLI and work from any directory):

```bash
# 0. Authenticate (once)
databricks auth login --host https://<your-workspace>.cloud.databricks.com

# 1. Confirm the CLI and inspect the bundle
databricks version
databricks bundle summary -t dev

# 2. Validate without deploying
databricks bundle validate -t dev            # or: scripts/validate.sh

# 3. Deploy to the development target
databricks bundle deploy -t dev              # or: scripts/deploy.sh

# 4. Run the sample job
databricks bundle run lakeflow_demo_job -t dev   # or: scripts/run.sh

# 5. Clean up the development deployment
scripts/destroy.sh dev --confirm             # protected: requires --confirm
```

> `databricks bundle destroy -t dev` is the raw command; `scripts/destroy.sh`
> adds a required `--confirm` guard.

## Inspect what was deployed

```bash
databricks bundle summary -t dev             # URLs for the deployed resources
```

- **Pipeline** → *Jobs & Pipelines → Pipelines*, named `[dev <you>] lakeflow_demo_pipeline`.
- **Job** → *Jobs & Pipelines → Jobs*, named `[dev <you>] lakeflow_demo_job`.
- **Tables** → *Catalog* → your catalog → your schema:
  `bronze_orders`, `silver_orders`, `gold_daily_category_revenue`.
- **Dashboard** → *Dashboards*, named `Lakeflow Demo -- Gold Metrics`.

## Expected results

- The pipeline reaches a **successful update** state and creates
  `bronze_orders` (~5,000 rows), `silver_orders` (slightly fewer — bad rows
  dropped), and `gold_daily_category_revenue` (one row per day/category/region).
- The Job's `refresh_pipeline` task completes, then `validate_gold` **passes**
  and prints something like `VALIDATION PASSED … rows=… total_revenue=…`.
- If the pipeline produced no Gold output, `validate_gold` **fails the Job**
  with a clear message (this is the safety net).
- The dashboard shows a total-revenue figure, a category bar chart, and a daily
  trend line (once `warehouse_id` is set and the dashboard points at the right
  schema).

## Verified end-to-end run (snapshot)

This bundle was deployed, run, and torn down on a real **AWS Databricks**
workspace (Unity Catalog + serverless). Transcript below (workspace host and run
ids generalized):

```text
$ databricks bundle validate -t dev
Validation OK!

$ databricks bundle deploy -t dev --var catalog=<catalog> --var warehouse_id=<id>
Uploading bundle files to /Workspace/Users/<user>/.bundle/aws-dab-lakeflow-starter/dev/files...
Deploying resources...
Updating deployment state...
Deployment complete!

$ databricks bundle run lakeflow_demo_job -t dev
Run URL: https://<workspace>/#job/<job_id>/run/<run_id>
2026-08-18 14:32:18 "[dev <user>] lakeflow_demo_job" RUNNING
2026-08-18 14:33:55 "[dev <user>] lakeflow_demo_job" TERMINATED SUCCESS
Output:
=======
Task validate_gold:
OK rows=60 total_revenue=81529.51
=======
Task demo_overview:
```

**Deployed resources** (`databricks bundle summary -t dev`):

| Type | Name |
| --- | --- |
| Pipeline | `[dev <user>] lakeflow_demo_pipeline` |
| Job | `[dev <user>] lakeflow_demo_job` |
| Dashboard | `[dev <user>] Lakeflow Demo -- Gold Metrics` |

**Tables produced** (verified via SQL after the run):

| Table | Rows | Notes |
| --- | ---: | --- |
| `bronze_orders` | 5,000 | synthetic raw orders |
| `silver_orders` | 4,940 | 60 "dirty" rows dropped by data-quality expectations |
| `gold_daily_category_revenue` | 60 | one row per (day, category, region); total revenue `81529.51` |

The row-drop count is exact and deterministic: 37 negative-quantity rows + 24
null-category rows − 1 overlapping row = 60 dropped, so Silver = 5,000 − 60 =
4,940. The `validate_gold` task confirmed the Gold output, and
`bundle destroy -t dev` removed every resource and table cleanly afterward.

## Customize the sample

See `docs/customization.md`. Common changes: swap synthetic data for your
tables, add a transformation or Job task, add/replace a notebook, edit the
dashboard, add an environment, change compute, add secrets and prod identities.

## Promote toward production

The same code deploys to `prod` with different, safer settings:

```bash
# Edit databricks.yml: set the prod workspace.root_path principal and the
# run_as / permissions identity (search for CHANGE_ME), then:
databricks bundle validate -t prod
databricks bundle deploy -t prod
```

`prod` uses `mode: production` (no name prefixing, deterministic paths, stricter
validation). Its deployment state lives under a single restricted Workspace
path — never `/Shared`. See `docs/architecture.md`.

## Run the local tests (optional, no workspace)

```bash
pip install pyyaml pytest
pytest -q
```

These offline checks validate file layout, config shape, resource references,
and that no secrets are committed. See `tests/README.md`.

## Common failures & fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `command not found: databricks` | CLI not installed | Install the CLI; `databricks version` |
| `default auth: cannot configure default credentials` | Not authenticated | `databricks auth login --host …` |
| `PERMISSION_DENIED` on catalog/schema | Missing UC grants | Ask an admin for `CREATE SCHEMA`/`CREATE TABLE` on the catalog |
| Pipeline serverless error | Serverless not enabled | Enable serverless, or switch to classic compute (`docs/customization.md`) |
| Dashboard deploy fails on `warehouse_id` | Placeholder not set | `--var warehouse_id=<id>` or set it per target |
| Prod validate 403 on the root_path | `CHANGE_ME_PROD_PRINCIPAL` not set | Set a real principal/path you can access |

Full guide: `docs/troubleshooting.md`.

## Documentation

- `docs/architecture.md` — how the bundle flows from Git to a running workload.
- `docs/customization.md` — how to adapt every part of the sample.
- `docs/troubleshooting.md` — symptom → cause → diagnostic → fix.
- `docs/customer-test-plan.md` — a short, repeatable acceptance test.
- `docs/ci-cd-integration.md` — optional GitHub Actions / Bitbucket / Azure DevOps.

## License

MIT — see `LICENSE`.
