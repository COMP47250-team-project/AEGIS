# Secrets Management — AEGIS

> Jira: **AEGIS-25** — Configure secrets management (GitHub Actions secrets + Azure Key Vault references).

This document is the source of truth for how AEGIS handles secrets. **No real secret value ever lives in git.** `.env` is git-ignored; only `.env.example` (placeholders) is committed.

## How secrets flow

```
Local dev:   .env.example  ──copy──▶  .env  (git-ignored, real values)
CI:          GitHub repo Settings ▶ Secrets and variables ▶ Actions
Production:  Azure Key Vault  ──ref──▶  Azure Container Apps env vars
```

## Required secrets

These **four** variables must be provisioned in **every** environment once access is available. They are documented with placeholders in [.env.example](.env.example).

| Variable | Purpose | GitHub Actions secret | Azure Key Vault secret |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | ⬜ to add | ⬜ to add |
| `AZURE_SERVICE_BUS_CONNECTION_STRING` | Telemetry event queue | ⬜ to add | ⬜ to add |
| `JWT_SECRET` | Signing key for auth tokens | ⬜ to add | ⬜ to add |
| `AZURE_CLIENT_ID` | Managed identity / service principal | ⬜ to add | ⬜ to add |

## TODO — once Azure / `gh` / `az` access is provisioned

These steps are **blocked** today (no Azure subscription, no `gh`/`az` CLI). Tracking them here so nothing is missed:

1. **GitHub Actions secrets** — add all four under repo *Settings ▶ Secrets and variables ▶ Actions*:
   ```bash
   gh secret set DATABASE_URL
   gh secret set AZURE_SERVICE_BUS_CONNECTION_STRING
   gh secret set JWT_SECRET
   gh secret set AZURE_CLIENT_ID
   ```
2. **Azure Key Vault** — store the same four secrets:
   ```bash
   az keyvault secret set --vault-name <aegis-kv> --name DATABASE-URL --value <...>
   # repeat for the others (Key Vault names use hyphens, not underscores)
   ```
3. **Container Apps** — wire each app env var to a Key Vault reference (secret ref + `secretRef` in the container template, or `@Microsoft.KeyVault(...)` reference) so the running app pulls values at startup with no plaintext in the deployment manifest.

## Guardrails

- `.env` is listed in [.gitignore](.gitignore) — real secrets cannot be tracked.
- A **gitleaks** pre-commit hook + CI scan should be added to block accidental secret commits. *(Not yet installed locally — TODO once tooling is available.)*
- Never paste real secret values into source, commits, PRs, or this file.
