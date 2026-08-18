"""Local, workspace-free static checks for the bundle.

These tests validate the *shape* of the repository and its configuration. They
do NOT contact a Databricks workspace, so they are safe and fast to run in CI
or before any deploy:

    pytest -q            # from the repo root

Checks that DO require a live workspace (schema validation, deploy, run) are
performed by `databricks bundle validate` and the scripts in scripts/ -- see
tests/README.md for the distinction.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip(
    "yaml", reason="PyYAML is required for the config tests (pip install pyyaml)"
)

# ---------------------------------------------------------------------------
# Helpers -- everything is resolved relative to the repo root so the tests run
# from any working directory.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(rel_path: str) -> dict:
    with (REPO_ROOT / rel_path).open() as fh:
        return yaml.safe_load(fh)


def resource_docs() -> dict:
    """Merge every resources/*.yml into one dict (like the bundle `include`)."""
    merged: dict = {"resources": {}}
    for path in sorted((REPO_ROOT / "resources").glob("*.yml")):
        doc = yaml.safe_load(path.read_text()) or {}
        for kind, defs in (doc.get("resources") or {}).items():
            merged["resources"].setdefault(kind, {}).update(defs)
    return merged


# ---------------------------------------------------------------------------
# 1. Required files exist
# ---------------------------------------------------------------------------
REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "databricks.yml",
    "resources/pipeline.yml",
    "resources/job.yml",
    "resources/dashboard.yml",
    "src/pipeline/transformations/bronze.py",
    "src/pipeline/transformations/silver.py",
    "src/pipeline/transformations/gold.py",
    "src/pipeline/README.md",
    "src/notebooks/validate_gold.py",
    "src/notebooks/demo_overview.py",
    "src/dashboards/lakeflow_demo.lvdash.json",
    "scripts/validate.sh",
    "scripts/deploy.sh",
    "scripts/run.sh",
    "scripts/destroy.sh",
    "docs/architecture.md",
    "docs/customization.md",
    "docs/troubleshooting.md",
    "docs/customer-test-plan.md",
    "docs/ci-cd-integration.md",
]


@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_required_file_exists(rel):
    assert (REPO_ROOT / rel).is_file(), f"missing required file: {rel}"


# ---------------------------------------------------------------------------
# 2. Root bundle config shape
# ---------------------------------------------------------------------------
def test_bundle_identity():
    cfg = load_yaml("databricks.yml")
    assert cfg["bundle"]["name"] == "aws-dab-lakeflow-starter"
    assert cfg["bundle"].get("uuid"), "bundle.uuid should be set"


def test_include_globs_resources():
    cfg = load_yaml("databricks.yml")
    assert "resources/*.yml" in cfg["include"]


def test_required_variables_declared():
    cfg = load_yaml("databricks.yml")
    for var in ("catalog", "schema", "warehouse_id"):
        assert var in cfg["variables"], f"variable '{var}' must be declared"


def test_targets_dev_and_prod():
    cfg = load_yaml("databricks.yml")
    targets = cfg["targets"]
    assert set(targets) >= {"dev", "prod"}
    assert targets["dev"].get("default") is True, "dev must be the default target"
    assert targets["dev"]["mode"] == "development"
    assert targets["prod"]["mode"] == "production"


def test_dev_and_prod_use_different_schema():
    cfg = load_yaml("databricks.yml")
    dev_schema = cfg["targets"]["dev"]["variables"]["schema"]
    prod_schema = cfg["targets"]["prod"]["variables"]["schema"]
    assert dev_schema != prod_schema, "dev and prod should not share a schema"


def test_prod_root_path_is_restricted():
    cfg = load_yaml("databricks.yml")
    root_path = cfg["targets"]["prod"]["workspace"]["root_path"]
    assert not root_path.startswith("/Shared"), "prod state must not live under /Shared"
    assert root_path.startswith("/Workspace/"), "prod root_path should be a Workspace path"


# ---------------------------------------------------------------------------
# 3. Resource definitions
# ---------------------------------------------------------------------------
def test_resource_keys_present():
    res = resource_docs()["resources"]
    assert "lakeflow_demo_pipeline" in res.get("pipelines", {})
    assert "lakeflow_demo_job" in res.get("jobs", {})
    assert "lakeflow_demo_dashboard" in res.get("dashboards", {})


def test_job_refreshes_the_bundle_pipeline():
    job = resource_docs()["resources"]["jobs"]["lakeflow_demo_job"]
    tasks = {t["task_key"]: t for t in job["tasks"]}
    assert "refresh_pipeline" in tasks
    ref = tasks["refresh_pipeline"]["pipeline_task"]["pipeline_id"]
    assert ref == "${resources.pipelines.lakeflow_demo_pipeline.id}", (
        "job must refresh the pipeline declared in the same bundle"
    )


def test_validate_task_depends_on_refresh():
    job = resource_docs()["resources"]["jobs"]["lakeflow_demo_job"]
    tasks = {t["task_key"]: t for t in job["tasks"]}
    assert "validate_gold" in tasks
    deps = [d["task_key"] for d in tasks["validate_gold"].get("depends_on", [])]
    assert "refresh_pipeline" in deps, "validate_gold must run after refresh_pipeline"


def test_pipeline_library_paths_exist():
    """The glob include path referenced by the pipeline must exist on disk.

    Bundle paths are relative to the file that declares them (resources/).
    """
    pipe = resource_docs()["resources"]["pipelines"]["lakeflow_demo_pipeline"]
    for lib in pipe["libraries"]:
        include = lib["glob"]["include"]  # e.g. ../src/pipeline/transformations/**
        base = include.split("**")[0].rstrip("/")
        resolved = (REPO_ROOT / "resources" / base).resolve()
        assert resolved.is_dir(), f"pipeline library path not found: {resolved}"


def test_notebook_task_paths_exist():
    job = resource_docs()["resources"]["jobs"]["lakeflow_demo_job"]
    for task in job["tasks"]:
        nb = task.get("notebook_task")
        if not nb:
            continue
        path = (REPO_ROOT / "resources" / nb["notebook_path"]).resolve()
        assert path.is_file(), f"notebook source not found: {path}"


def test_dashboard_file_path_exists_and_is_json():
    dash = resource_docs()["resources"]["dashboards"]["lakeflow_demo_dashboard"]
    path = (REPO_ROOT / "resources" / dash["file_path"]).resolve()
    assert path.is_file(), f"dashboard file not found: {path}"
    doc = json.loads(path.read_text())
    assert doc.get("datasets"), "dashboard must declare datasets"
    assert doc.get("pages"), "dashboard must declare at least one page"
    # At least two visualization widgets (excluding the title text widget).
    widgets = [w["widget"] for p in doc["pages"] for w in p["layout"]]
    charts = [w for w in widgets if "spec" in w]
    assert len(charts) >= 2, "dashboard should have at least two visualizations"


# ---------------------------------------------------------------------------
# 4. No credential-like values are committed
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    re.compile(r"dapi[0-9a-fA-F]{16,}"),               # Databricks PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),                    # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),  # private key
    # A secret-like assignment: password/secret/token = a long, space-free,
    # non-placeholder value (real secrets look like this; "token: write" does not).
    re.compile(r"(?i)\b(password|client_secret|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9+/=_\-]{16,}"),
]
# Values that are obviously placeholders / env indirections are allowed.
ALLOWLIST = ("CHANGE_ME", "example.com", "<your", "your_email", "$(", "${")


def _iter_repo_text_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if parts & {".git", ".databricks", "__pycache__", ".venv", "node_modules"}:
            continue
        try:
            yield path, path.read_text()
        except (UnicodeDecodeError, OSError):
            continue


def test_no_committed_secrets():
    offenders = []
    for path, text in _iter_repo_text_files():
        if path.name == "test_configuration.py":
            continue  # this file legitimately contains the patterns themselves
        for line in text.splitlines():
            if any(a in line for a in ALLOWLIST):
                continue
            for pat in SECRET_PATTERNS:
                if pat.search(line):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {line.strip()[:80]}")
    assert not offenders, "possible committed secret(s):\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# 5. README / script internal consistency
# ---------------------------------------------------------------------------
def test_readme_mentions_job_key_and_scripts():
    readme = (REPO_ROOT / "README.md").read_text()
    assert "lakeflow_demo_job" in readme, "README should reference the job resource key"
    for script in ("validate.sh", "deploy.sh", "run.sh", "destroy.sh"):
        assert script in readme, f"README should mention scripts/{script}"


def test_scripts_are_shell_and_safe():
    destroy = (REPO_ROOT / "scripts" / "destroy.sh").read_text()
    # destroy must require an explicit confirmation flag.
    assert "--confirm" in destroy, "destroy.sh must require --confirm"
    for name in ("validate.sh", "deploy.sh", "run.sh", "destroy.sh"):
        text = (REPO_ROOT / "scripts" / name).read_text()
        assert text.startswith("#!/usr/bin/env bash") or text.startswith("#!/bin/bash")
        assert "set -euo pipefail" in text, f"{name} should use strict mode"
