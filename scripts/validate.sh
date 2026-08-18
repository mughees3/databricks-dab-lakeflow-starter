#!/usr/bin/env bash
# =============================================================================
# validate.sh -- parse and schema-validate the bundle (no deploy).
#
# Usage:   scripts/validate.sh [target]      (target defaults to 'dev')
# Example: scripts/validate.sh
#          scripts/validate.sh prod
# =============================================================================
set -euo pipefail

# Resolve the repo root so this works from any directory.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TARGET="${1:-dev}"

# --- Preconditions ---------------------------------------------------------
if ! command -v databricks >/dev/null 2>&1; then
  echo "ERROR: the Databricks CLI is not installed or not on PATH." >&2
  echo "       Install it: https://docs.databricks.com/aws/en/dev-tools/cli/install" >&2
  exit 1
fi

echo "Databricks CLI: $(databricks version)"
echo "Target        : ${TARGET}"
echo "Repo root     : ${REPO_ROOT}"
echo

# --- Validate --------------------------------------------------------------
# `bundle validate` parses the YAML, resolves variables/substitutions, and
# checks the config against the current bundle schema. It does not deploy.
databricks bundle validate -t "${TARGET}"

echo
echo "OK: bundle is valid for target '${TARGET}'."
