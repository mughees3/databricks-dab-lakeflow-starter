# Customer test plan (acceptance test)

A short, repeatable test a customer or solutions engineer can run in a
**non-production** workspace to confirm the bundle works end to end. ~15 minutes.

## Prerequisites

- Databricks CLI v0.218+ (`databricks version`).
- An AWS Databricks workspace with **Unity Catalog** and **serverless** enabled.
- Rights to create schemas/tables in a catalog (default `main`), and to create
  jobs, pipelines, and (optionally) a dashboard.
- A running **SQL warehouse** id if you want to test the dashboard
  (`databricks warehouses list`).
- Authenticated CLI: `databricks auth login --host https://<workspace>.cloud.databricks.com`.

## Steps

| # | Action | Command | Expected output | Evidence to capture |
| --- | --- | --- | --- | --- |
| 1 | Confirm CLI | `databricks version` | `Databricks CLI vX.Y.Z` (≥ 0.218) | version string |
| 2 | Confirm auth | `databricks current-user me` | your user record (JSON) | username |
| 3 | Local static checks (optional) | `pip install pyyaml pytest && pytest -q` | all tests pass | `N passed` line |
| 4 | Validate | `databricks bundle validate -t dev` | `Validation OK!` | terminal output |
| 5 | Inspect plan | `databricks bundle summary -t dev` | pipeline/job/dashboard listed with your `[dev <you>]` names | summary text |
| 6 | Deploy | `databricks bundle deploy -t dev` | `Deployment complete!` | terminal output |
| 7 | Run the Job | `databricks bundle run lakeflow_demo_job -t dev` | run reaches **SUCCESS**; all tasks green | run URL + status |
| 8 | Verify tables | `databricks tables list main <your_schema>` | `bronze_orders`, `silver_orders`, `gold_daily_category_revenue` | table list |
| 9 | Verify validation | (read task output from step 7) | `VALIDATION PASSED … rows=… total_revenue=…` | task output |
| 10 | (Optional) Dashboard | set `warehouse_id`, redeploy, open dashboard | counter + bar + line render | screenshot |
| 11 | Clean up | `scripts/destroy.sh dev --confirm` | `destroyed target 'dev'` | terminal output |

> Your dev schema is per-user (`<you>_lakeflow_demo`); substitute it in step 8.

## Negative test (the safety net works)

Prove that `validate_gold` fails loudly when Gold is absent:

1. `databricks bundle run lakeflow_demo_job -t dev -- --schema does_not_exist`
   (overrides the schema so the Gold table won't be found).
2. **Expected:** the `validate_gold` task **fails** with
   `VALIDATION FAILED: Gold table … does not exist`.
3. Capture the failing task message as evidence, then re-run step 7 normally.

## Pass criteria

- Steps 4, 6, 7 succeed; step 8 shows all three tables; step 9 shows
  `VALIDATION PASSED`.
- The negative test fails at `validate_gold` with a clear message.
- Step 11 removes the deployed resources cleanly.

## Cleanup

`scripts/destroy.sh dev --confirm` deletes the deployed job, pipeline, and
dashboard for the dev target (and the pipeline's managed tables). Confirm with
`databricks bundle summary -t dev` afterward (should report nothing deployed).
