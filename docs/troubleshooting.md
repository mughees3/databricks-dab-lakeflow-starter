# Troubleshooting

Each entry: **symptoms → likely cause → diagnostic → remediation**. Most issues
surface during `databricks bundle validate` or `deploy`.

---

## 1. CLI not installed or too old

- **Symptoms:** `command not found: databricks`; or errors about unknown flags
  / unsupported bundle fields.
- **Cause:** the CLI is missing or is an old (0.x) build.
- **Diagnostic:** `databricks version` (expect v0.218+; verified on v1.0.0).
- **Remediation:** install/upgrade —
  <https://docs.databricks.com/aws/en/dev-tools/cli/install>. The legacy
  `pip install databricks-cli` package is **not** the bundle-aware CLI.

## 2. Authentication failure

- **Symptoms:** `default auth: cannot configure default credentials`;
  `cannot get workspace client`; 401/403 immediately.
- **Cause:** no valid auth context for the target workspace.
- **Diagnostic:** `databricks current-user me` (add `-p <profile>` to test one).
- **Remediation:** `databricks auth login --host https://<workspace>.cloud.databricks.com`,
  or set `DATABRICKS_HOST`/`DATABRICKS_TOKEN`, or pass `-p <profile>`.

## 3. Unity Catalog permission failure

- **Symptoms:** `PERMISSION_DENIED` creating a schema/table; pipeline update
  fails writing to the catalog.
- **Cause:** the deploying/run-as identity lacks UC grants.
- **Diagnostic:** `databricks catalogs list`; try
  `databricks schemas create <schema> <catalog>` manually.
- **Remediation:** ask a metastore admin for `USE CATALOG` + `CREATE SCHEMA` on
  the catalog (and `CREATE TABLE` on the schema), or point `--var catalog=/schema=`
  at a catalog/schema you already own.

## 4. Invalid catalog or schema

- **Symptoms:** `Catalog 'x' does not exist`; `Schema 'y' does not exist`.
- **Cause:** the configured catalog/schema isn't present (or a typo).
- **Diagnostic:** `databricks catalogs list`; check `variables:` in
  `databricks.yml` and any `--var` overrides.
- **Remediation:** create them, or set existing values via `--var` or the
  target's `variables:`. The default `main` catalog exists in most workspaces.

## 5. Unsupported pipeline or Job field

- **Symptoms:** `bundle validate` errors like `unknown field` /
  `additional properties are not allowed`.
- **Cause:** a field name is wrong or belongs to a different CLI version.
- **Diagnostic:** `databricks bundle schema > schema.json` and search it; compare
  against <https://docs.databricks.com/aws/en/dev-tools/bundles/resources>.
- **Remediation:** correct the field; upgrade the CLI if the field is newer than
  your version.

## 6. Pipeline source path not found

- **Symptoms:** deploy warns/errors that a library or glob matches nothing.
- **Cause:** paths in `resources/pipeline.yml` are relative to that file
  (`resources/`), so they start with `../src/…`.
- **Diagnostic:** `databricks bundle validate -t dev -o json | jq '.resources.pipelines'`
  and check the resolved `libraries`/`root_path`. Or run `pytest -q`
  (`test_pipeline_library_paths_exist`).
- **Remediation:** fix the relative path; ensure the files exist under
  `src/pipeline/transformations/`.

## 7. Job cannot resolve the pipeline resource

- **Symptoms:** `cannot resolve ${resources.pipelines.…}`; deploy fails on the
  `refresh_pipeline` task.
- **Cause:** the reference key doesn't match the pipeline resource key.
- **Diagnostic:** confirm the key in `resources/pipeline.yml`
  (`lakeflow_demo_pipeline`) matches the `pipeline_id:` reference in
  `resources/job.yml`.
- **Remediation:** align the keys. Reference the id, not a name:
  `${resources.pipelines.lakeflow_demo_pipeline.id}`.

## 8. Notebook task cannot resolve its source path

- **Symptoms:** `notebook not found`; task fails to start.
- **Cause:** wrong `notebook_path`, or the file lacks the
  `# Databricks notebook source` header (so it deploys as a plain file, not a
  notebook).
- **Diagnostic:** `databricks bundle validate -t dev -o json | jq '.resources.jobs.lakeflow_demo_job.tasks[].notebook_task'`
  — the resolved path should be a workspace path with **no** extension.
- **Remediation:** keep the header as the first line; reference the file as
  `../src/notebooks/<name>.py`.

## 9. Dashboard resource or serialized definition fails validation

- **Symptoms:** deploy fails on the dashboard; `invalid dashboard`; missing
  `warehouse_id`.
- **Cause:** `warehouse_id` still `CHANGE_ME`, or the `.lvdash.json` has an
  invalid widget/dataset shape.
- **Diagnostic:** `databricks warehouses list` for a real id;
  `jq empty src/dashboards/lakeflow_demo.lvdash.json` to confirm valid JSON.
- **Remediation:** set `--var warehouse_id=<id>` (or per target). For widget/spec
  errors, edit the dashboard in the UI and re-export the JSON (see
  `docs/customization.md`).

## 10. Pipeline succeeds but validation can't find the Gold output

- **Symptoms:** `validate_gold` fails with `Gold table … does not exist` or
  `has 0 rows`, even though the pipeline update was green.
- **Cause:** the notebook's `catalog`/`schema` don't match where the pipeline
  wrote (common when the dashboard/notebook default differs from the target).
- **Diagnostic:** compare the Job's `catalog`/`schema` parameters to the
  pipeline's resolved `catalog`/`schema`
  (`… -o json | jq '.resources.pipelines.lakeflow_demo_pipeline | {catalog,schema}'`).
  Check the tables exist: `databricks tables list <catalog> <schema>`.
- **Remediation:** ensure the Job parameters and the pipeline use the same
  variables (they do by default — both bind to `${var.catalog}`/`${var.schema}`).

## 11. Deployment collision between users

- **Symptoms:** two engineers overwrite each other; unexpected `[dev X]` names.
- **Cause:** not using `mode: development`, or a shared `root_path`.
- **Diagnostic:** `databricks bundle summary -t dev` — confirm the path is under
  your own `/Workspace/Users/<you>/.bundle/…` and names are `[dev <you>]`.
- **Remediation:** keep dev in `mode: development` (it isolates state, names, and
  the per-user schema). Never point dev state at `/Shared`.

## 12. Prod validate/deploy 403 on the root_path

- **Symptoms:** `does not have View/Manage permissions`; `unable to create
  directory at /Workspace/Users/CHANGE_ME_PROD_PRINCIPAL/…`.
- **Cause:** the prod `workspace.root_path` still contains the `CHANGE_ME`
  placeholder (a principal you can't write to).
- **Diagnostic:** grep `CHANGE_ME` in `databricks.yml`.
- **Remediation:** set the prod `root_path` to a Workspace path you (or your
  service principal) can write to, and set `run_as`/`permissions` to a real
  identity.

## 13. Safe cleanup after a failed deployment

- **Symptoms:** partial resources left after an error.
- **Diagnostic:** `databricks bundle summary -t <target>`.
- **Remediation:** `scripts/destroy.sh <target> --confirm` (wraps
  `databricks bundle destroy -t <target> --auto-approve`). If state is corrupt,
  remove the local `.databricks/` folder and re-deploy; as a last resort delete
  the target's `root_path` in the workspace, then redeploy.
