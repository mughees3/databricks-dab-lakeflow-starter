# Optional CI/CD integration

The **primary, fully supported path for this repo is the local Databricks CLI**
(see the README). Nothing here is a prerequisite. This document shows how to
wire the *same* bundle — unchanged — into GitHub Actions, Bitbucket Pipelines,
or Azure DevOps. Pick one; the bundle structure does not change.

> **Verify before you ship.** CI/CD auth and provider syntax change. The
> examples below are patterns, not guarantees — confirm every auth detail
> against the current official docs (linked per section) and replace every
> `CHANGE_ME` with your own value. **Never print or commit secrets**, and pin
> action/CLI versions.

## The promotion flow (identical for all three providers)

```
Pull request or merge request
        |
        v
Checkout -> unit tests -> bundle validate
        |
        v
Deploy and smoke-test dev/staging target
        |
        v
Approval gate
        |
        v
Validate and deploy prod target
```

- **unit tests** = the offline `pytest -q` from `tests/`.
- **smoke test** = `databricks bundle run lakeflow_demo_job -t <target>`.
- **approval gate** = a protected environment / manual approval before prod.

## CI/CD auth vs data-plane / cloud auth — keep them separate

- **CI/CD → Databricks control plane:** a **Databricks service principal**
  (OAuth M2M, ideally via OIDC workload identity federation). This is what runs
  `databricks bundle …`. That is all these pipelines need.
- **Cloud / AWS data-plane auth** (instance profiles, S3 access, the workspace's
  cross-account role) is configured **inside** the Databricks workspace, not in
  the CI system. Do **not** put AWS `ARM_*`/Azure credentials in these
  pipelines — they are unrelated to deploying a bundle to an AWS workspace.

---

## GitHub Actions

Official refs:
- CLI setup action: <https://github.com/databricks/setup-cli>
- Databricks CI/CD with bundles: <https://docs.databricks.com/aws/en/dev-tools/bundles/ci-cd>
- OAuth token federation (OIDC): <https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation>
- GitHub OIDC concepts: <https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect>

### Preferred: OIDC workload identity federation (no stored secret)

1. **Databricks side:** create a service principal and add a **federation
   policy** that trusts your GitHub repo. Restrict the subject claim to the
   exact repo + branch/environment, e.g.
   `repo:CHANGE_ME_ORG/CHANGE_ME_REPO:environment:prod` (or
   `:ref:refs/heads/main`). Grant that service principal only the workspace
   permissions it needs (deploy the bundle's resources).
2. **GitHub side:** grant the service principal deploy rights, protect the
   `prod` environment with required reviewers, and use least-privilege job
   permissions.

```yaml
# .github/workflows/deploy.yml
name: deploy-bundle
on:
  pull_request:
  push:
    branches: [main]

permissions:
  id-token: write      # REQUIRED: lets the job mint a GitHub OIDC token
  contents: read       # REQUIRED: checkout

env:
  DATABRICKS_HOST: https://CHANGE_ME-workspace.cloud.databricks.com
  DATABRICKS_CLIENT_ID: CHANGE_ME_SERVICE_PRINCIPAL_APP_ID
  DATABRICKS_AUTH_TYPE: github-oidc     # CLI exchanges the GitHub OIDC token

jobs:
  validate-dev:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@v1.12.1        # pin the version
      - name: Unit tests
        run: |
          python -m pip install pyyaml pytest
          pytest -q
      - run: databricks bundle validate -t dev
      - run: databricks bundle deploy -t dev
      - run: databricks bundle run lakeflow_demo_job -t dev   # smoke test

  deploy-prod:
    needs: validate-dev
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: prod            # protected env -> required reviewers = approval gate
    steps:
      - uses: actions/checkout@v4
      - uses: databricks/setup-cli@v1.12.1
      - run: databricks bundle validate -t prod
      - run: databricks bundle deploy -t prod
```

### Fallback: service-principal OAuth secret (only if OIDC is unavailable)

Store a service-principal client id/secret as **encrypted repository or
environment secrets** and reference them as env vars
(`DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`, `DATABRICKS_HOST`) with
`DATABRICKS_AUTH_TYPE: oauth-m2m`. Never echo them. Prefer OIDC.

---

## Bitbucket Pipelines

There is **no** Databricks-specific Bitbucket pipe — install and call the CLI
directly.

Official refs:
- Bitbucket OIDC: <https://support.atlassian.com/bitbucket-cloud/docs/integrate-pipelines-with-resource-servers-using-oidc/>
- Databricks OAuth token federation: <https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation>

### Preferred: OIDC with a Databricks service principal

- **Databricks side:** federation policy restricted to the exact workspace,
  repository, branch, and deployment environment.
- **Bitbucket side:** enable OIDC on the step (`oidc: true`). Bitbucket exposes
  the token as `BITBUCKET_STEP_OIDC_TOKEN`. Store non-secret config
  (`DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`) as **secured repository
  variables**; protect `main`; require a **manual** step before prod. **Confirm
  the exact CLI env var/mechanism for consuming the OIDC token in the current
  Databricks docs** before relying on this.

```yaml
# bitbucket-pipelines.yml
image: python:3.11
definitions:
  steps:
    - step: &install-cli
        name: Install Databricks CLI
        script:
          - curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/v1.12.1/install.sh | sh
          - databricks version

pipelines:
  branches:
    main:
      - step:
          <<: *install-cli
          name: Validate + deploy dev (smoke test)
          oidc: true
          script:
            - pip install pyyaml pytest && pytest -q
            - export DATABRICKS_HOST=$DATABRICKS_HOST                 # secured repo var
            - export DATABRICKS_CLIENT_ID=$DATABRICKS_CLIENT_ID       # secured repo var
            # Consume $BITBUCKET_STEP_OIDC_TOKEN per current Databricks OIDC docs.
            - databricks bundle validate -t dev
            - databricks bundle deploy -t dev
            - databricks bundle run lakeflow_demo_job -t dev
      - step:
          <<: *install-cli
          name: Deploy prod
          deployment: production        # deployment env permissions = gate
          trigger: manual               # manual production gate
          oidc: true
          script:
            - databricks bundle validate -t prod
            - databricks bundle deploy -t prod
```

Security: secured repository variables (masked in logs), deployment-environment
permissions, protected branches, a manual prod gate, and a pinned CLI version.

---

## Azure DevOps (targeting an AWS Databricks workspace)

Azure Pipelines can deploy to an **AWS** Databricks workspace. Do **not** import
Azure Resource Manager auth (`AzureCLI@2`, `ARM_*` variables) — they are
irrelevant here. Authenticate with a **Databricks service principal**.

Official refs:
- Azure Pipelines: <https://learn.microsoft.com/en-us/azure/devops/pipelines/>
- Databricks OAuth token federation: <https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation>

```yaml
# azure-pipelines.yml
trigger:
  branches: { include: [ main ] }

pool: { vmImage: ubuntu-latest }

variables:
  # Non-secret. Store the client id/secret as SECRET pipeline variables or in an
  # approved secret store (e.g. Azure Key Vault via a variable group) - never inline.
  DATABRICKS_HOST: https://CHANGE_ME-workspace.cloud.databricks.com

stages:
  - stage: dev
    jobs:
      - job: validate_deploy_dev
        steps:
          - checkout: self
          - script: |
              curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/v1.12.1/install.sh | sh
              databricks version
            displayName: Install Databricks CLI (pinned)
          - script: |
              python -m pip install pyyaml pytest && pytest -q
            displayName: Unit tests
          - script: |
              databricks bundle validate -t dev
              databricks bundle deploy -t dev
              databricks bundle run lakeflow_demo_job -t dev
            displayName: Validate + deploy + smoke test (dev)
            env:
              DATABRICKS_CLIENT_ID: $(DATABRICKS_CLIENT_ID)       # secret var
              DATABRICKS_CLIENT_SECRET: $(DATABRICKS_CLIENT_SECRET)  # secret var
              DATABRICKS_AUTH_TYPE: oauth-m2m

  - stage: prod
    dependsOn: dev
    condition: succeeded()
    jobs:
      - deployment: deploy_prod
        environment: prod           # ADO Environment -> approvals & checks = gate
        strategy:
          runOnce:
            deploy:
              steps:
                - checkout: self
                - script: |
                    curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/v1.12.1/install.sh | sh
                    databricks bundle validate -t prod
                    databricks bundle deploy -t prod
                  displayName: Validate + deploy (prod)
                  env:
                    DATABRICKS_CLIENT_ID: $(DATABRICKS_CLIENT_ID)
                    DATABRICKS_CLIENT_SECRET: $(DATABRICKS_CLIENT_SECRET)
                    DATABRICKS_AUTH_TYPE: oauth-m2m
```

Prefer OIDC/workload identity federation over a stored secret where your ADO
setup supports it; if federation is unavailable, use rotated secret variables or
an approved external secret store. Apply branch policies, ADO Environments with
approvals, secret masking, least privilege, separate service principals per
target, and auditability.

---

## Checklist for any provider

- [ ] Verified auth details against current Databricks + provider docs.
- [ ] Service principal (not a personal account) with least-privilege scope.
- [ ] OIDC federation preferred; secrets only as a rotated fallback.
- [ ] Federation policy / secret restricted to the exact repo, branch, and env.
- [ ] `id-token: write` (or provider equivalent) enabled only where needed.
- [ ] Action/CLI versions pinned (`databricks/setup-cli@v1.12.1`).
- [ ] Protected branches + manual approval before prod.
- [ ] No secrets printed; logs masked.
- [ ] CI/CD auth kept distinct from AWS data-plane auth.
