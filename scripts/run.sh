#!/usr/bin/env bash
# =============================================================================
# run.sh -- run the sample Job (refresh pipeline -> validate Gold -> overview).
#
# Usage:   scripts/run.sh [target] [job_key]
#          target   defaults to 'dev'
#          job_key  defaults to 'lakeflow_demo_job'
# Example: scripts/run.sh
#          scripts/run.sh dev lakeflow_demo_job
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET="${1:-dev}"
JOB_KEY="${2:-lakeflow_demo_job}"

if ! command -v databricks >/dev/null 2>&1; then
  echo "ERROR: the Databricks CLI is not installed or not on PATH." >&2
  exit 1
fi

echo "Target : ${TARGET}"
echo "Job    : ${JOB_KEY}"
if [[ "${TARGET}" == "prod" ]]; then
  echo "NOTE: running against PROD (explicitly selected)."
fi
echo

# `bundle run` triggers the resource and streams its status until completion.
databricks bundle run "${JOB_KEY}" -t "${TARGET}"
