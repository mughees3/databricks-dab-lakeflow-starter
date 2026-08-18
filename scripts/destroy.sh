#!/usr/bin/env bash
# =============================================================================
# destroy.sh -- tear down everything the bundle deployed to a target.
#
# DESTRUCTIVE. Requires an explicit --confirm flag so it can never run by
# accident. It deletes the deployed jobs, pipelines, and dashboard for the
# target (and the pipeline's managed tables).
#
# Usage:   scripts/destroy.sh [target] --confirm
# Example: scripts/destroy.sh dev --confirm
#          scripts/destroy.sh prod --confirm
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET="dev"
CONFIRM="false"

# Parse args: an optional target plus the required --confirm flag, any order.
for arg in "$@"; do
  case "$arg" in
    --confirm) CONFIRM="true" ;;
    -*)        echo "ERROR: unknown flag '$arg'" >&2; exit 2 ;;
    *)         TARGET="$arg" ;;
  esac
done

if ! command -v databricks >/dev/null 2>&1; then
  echo "ERROR: the Databricks CLI is not installed or not on PATH." >&2
  exit 1
fi

if [[ "${CONFIRM}" != "true" ]]; then
  echo "Refusing to destroy without confirmation." >&2
  echo "This will DELETE the deployed resources for target '${TARGET}'." >&2
  echo "Re-run with the explicit flag:" >&2
  echo "    scripts/destroy.sh ${TARGET} --confirm" >&2
  exit 1
fi

echo "Destroying bundle deployment for target: ${TARGET}"
if [[ "${TARGET}" == "prod" ]]; then
  echo "WARNING: destroying PROD resources (explicitly selected)."
fi
echo

# --auto-approve avoids a second interactive prompt now that --confirm was given.
databricks bundle destroy -t "${TARGET}" --auto-approve

echo
echo "OK: destroyed target '${TARGET}'."
