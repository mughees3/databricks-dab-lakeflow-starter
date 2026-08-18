# Tests

Two clearly separated layers of checking.

## 1. Local static checks (no workspace required)

`test_configuration.py` runs entirely offline. It verifies the *shape* of the
repo and config so you catch mistakes before spending time on a deploy:

- every required file exists;
- `databricks.yml` has the expected bundle name, variables, and dev/prod targets;
- dev is the default and uses `mode: development`; prod uses `mode: production`;
- prod deployment state is not under `/Shared`;
- the pipeline / job / dashboard resource keys exist;
- the Job refreshes the pipeline declared in the same bundle, and the validation
  task depends on the refresh;
- the pipeline library glob, notebook sources, and dashboard file all exist on disk;
- no credential-like values are committed;
- the README and scripts are internally consistent (job key, script names,
  `destroy.sh --confirm`, strict-mode shell).

Run them:

```bash
# from the repo root
pip install pyyaml pytest      # one-time (or: uv pip install -r ...)
pytest -q
```

## 2. Live checks (require a configured workspace)

These are NOT in pytest because they need authentication and a real workspace:

| Check | Command |
| --- | --- |
| Bundle parses & schema-validates | `databricks bundle validate -t dev` (or `scripts/validate.sh`) |
| Resources deploy | `databricks bundle deploy -t dev` (or `scripts/deploy.sh`) |
| Pipeline runs and Gold validates | `databricks bundle run lakeflow_demo_job -t dev` (or `scripts/run.sh`) |

See `docs/customer-test-plan.md` for the full acceptance test.
