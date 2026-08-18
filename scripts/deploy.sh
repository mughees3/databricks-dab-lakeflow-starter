#!/usr/bin/env bash
# =============================================================================
# deploy.sh -- validate, then deploy the bundle to a target.
#
# Usage:   scripts/deploy.sh [target]        (target defaults to 'dev')
# Example: scripts/deploy.sh                 # deploys to dev
#          scripts/deploy.sh prod            # PROD must be requested explicitly
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET="${1:-dev}"

if ! command -v databricks >/dev/null 2>&1; then
  echo "ERROR: the Databricks CLI is not installed or not on PATH." >&2
  echo "       Install it: https://docs.databricks.com/aws/en/dev-tools/cli/install" >&2
  exit 1
fi

# Fail early with a helpful message if auth is not configured.
if ! databricks current-user me >/dev/null 2>&1; then
  echo "ERROR: not authenticated. Run 'databricks auth login --host <workspace-url>'" >&2
  echo "       or set a profile with -p / the DATABRICKS_HOST env var." >&2
  exit 1
fi

echo "Databricks CLI : $(databricks version)"
echo "Deploy target  : ${TARGET}"
echo "Deploying as   : $(databricks current-user me --output json | (command -v jq >/dev/null && jq -r .userName || cat))"
if [[ "${TARGET}" == "prod" ]]; then
  echo "NOTE: deploying to PROD (explicitly selected)."
fi
echo

# Validate first (cheap) so a bad config never reaches deploy.
databricks bundle validate -t "${TARGET}"
echo
databricks bundle deploy -t "${TARGET}"

echo
echo "OK: deployed to target '${TARGET}'."
echo "Next: scripts/run.sh ${TARGET}   # run the sample job"
