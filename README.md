<a name="readme-top"></a>

<div align="center">

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Apache License][license-shield]][license-url]
[![CI][ci-shield]][ci-url]

</div>

<br />

<div align="center">
  <h1>AEGIS</h1>
  <p><strong>Adaptive Exam Guardian and Integrity System</strong></p>
  <p>
    A browser-native anti-cheat exam portal that monitors student behaviour in real time using privacy-minimised telemetry, scores six signals into a single confidence score, and surfaces integrity reports for human review — without webcams, browser extensions, or invasive surveillance.
  </p>
  <p>
    <a href="http://localhost:8000/docs"><strong>API Docs (local) »</strong></a>
    &nbsp;·&nbsp;
    <a href="https://github.com/COMP47250-team-project/AEGIS/issues/new?labels=bug">Report Bug</a>
    &nbsp;·&nbsp;
    <a href="https://github.com/COMP47250-team-project/AEGIS/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

---

## Table of Contents

<details>
  <summary>Expand</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#core-design-principles">Core Design Principles</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#option-a--docker-compose-recommended">Option A — Docker Compose (recommended)</a></li>
        <li><a href="#option-b--manual-local-setup">Option B — Manual local setup</a></li>
      </ul>
    </li>
    <li><a href="#environment-variables">Environment Variables</a></li>
    <li><a href="#running-tests--ci-checks">Running Tests & CI Checks</a></li>
    <li><a href="#azure-environment-aegis-21">Azure Environment</a></li>
    <li><a href="#project-structure">Project Structure</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

---

## About The Project

AEGIS is built by a 6-person MSc Computer Science team at University College Dublin for the **COMP47250 Team Software Project** (Microsoft partnership, 2026).

Professors create and schedule online exams. During an exam, the student's browser emits privacy-minimised telemetry (tab visibility, paste events, keystroke intervals, window focus/blur, answer timing). A scoring engine combines these six signals into a 0–1 confidence score. After the exam, professors review a flagged-event timeline and decide whether to investigate — no automatic academic-misconduct verdicts are ever issued.

### Core Design Principles

- **Non-blocking** — telemetry collection and answer submission are fully independent; a network hiccup never pauses the exam.
- **Privacy by design** — event metadata only; no key content, clipboard text, screen recordings, or biometrics.
- **Human review** — the system provides evidence for professors, not verdicts.
- **Data minimisation** — six behavioural signals, nothing more.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

[![FastAPI][fastapi-badge]][fastapi-url]
[![Python][python-badge]][python-url]
[![React][react-badge]][react-url]
[![TypeScript][typescript-badge]][typescript-url]
[![Vite][vite-badge]][vite-url]
[![TailwindCSS][tailwind-badge]][tailwind-url]
[![PostgreSQL][postgres-badge]][postgres-url]
[![Docker][docker-badge]][docker-url]
[![Azure][azure-badge]][azure-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Getting Started

### Prerequisites

| Tool | Minimum version | Check |
|------|----------------|-------|
| Docker + Docker Compose | 24.x / 2.x | `docker --version` |
| Node.js (for manual setup) | 22 | `node --version` |
| uv (for manual setup) | 0.4+ | `uv --version` |
| PostgreSQL (for manual setup) | 16 | `psql --version` |

Install uv via the [official installer](https://docs.astral.sh/uv/getting-started/installation/): `curl -LsSf https://astral.sh/uv/install.sh \| sh`

---

### Option A — Docker Compose (recommended)

This spins up **PostgreSQL 16**, the **FastAPI backend** (with Alembic migrations), the **React/Vite frontend**, and an **Azurite** Azure Storage emulator — all with hot-reload.

```sh
# 1. Clone the repository
git clone https://github.com/COMP47250-team-project/AEGIS.git
cd AEGIS

# 2. Create the frontend env file (defaults work for Docker)
cp frontend/env.example frontend/.env

# 3. (Optional) Set a real JWT secret — defaults to a dev placeholder
export JWT_SECRET_KEY="$(openssl rand -hex 32)"

# 4. Build and start all services
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Azurite Blob | http://localhost:10000 |

To stop and remove volumes (wipes database):

```sh
docker compose down -v
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

### Option B — Manual local setup

Use this path when you want faster iteration on a single service without Docker.

#### 1. PostgreSQL

Create a database and user for local development:

```sql
CREATE USER dev WITH PASSWORD 'dev';
CREATE DATABASE appdb OWNER dev;
```

#### 2. Backend

```sh
cd backend

# Install all dependencies (creates .venv automatically)
uv sync

# Set required environment variables
export DATABASE_URL="postgresql+asyncpg://dev:dev@localhost:5432/appdb"
export DATABASE_URL_SYNC="postgresql://dev:dev@localhost:5432/appdb"
export JWT_SECRET_KEY="change_me_to_a_random_64_char_string"

# Run database migrations
uv run alembic upgrade head

# Start the development server (hot-reload)
uv run uvicorn app.main:app --reload
```

The API is now available at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

#### 3. Frontend

```sh
cd frontend

# Copy env file and configure API URL
cp env.example .env
# .env already points to http://localhost:8000 by default

# Install dependencies
npm install

# Start the development server (HMR)
npm run dev
```

The app is now available at http://localhost:5173.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Environment Variables

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://aegis:aegis_dev_pw@localhost:5432/aegis` | Async PostgreSQL connection string (asyncpg) |
| `DATABASE_URL_SYNC` | Yes | `postgresql://aegis:aegis_dev_pw@localhost:5432/aegis` | Sync connection string for Alembic migrations |
| `JWT_SECRET_KEY` | Yes | `change_me_to_a_random_64_char_string` | Secret used to sign JWTs — **change in production** |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | No | `480` | Token lifetime in minutes (8 hours) |
| `APP_ENV` | No | `development` | Application environment (`development` / `production`) |
| `LOG_LEVEL` | No | `DEBUG` | Uvicorn log level |
| `AZURE_SERVICE_BUS_CONNECTION_STRING` | No | — | Azure Service Bus connection string; telemetry dispatch is skipped if unset |
| `AZURE_SERVICE_BUS_QUEUE_NAME` | No | `telemetry-events` | Queue name for telemetry events |

### Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | Yes | `http://localhost:8000` | Base URL of the FastAPI backend |

> **Security note:** Never commit `.env` files. Both `.env` files are already listed in `.gitignore`. Use the provided `*.example` files as templates.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Running Tests & CI Checks

The CI pipeline runs two independent jobs on every push and pull request to `main`.

### Backend (Python)

```sh
cd backend

# Lint (ruff)
uv run ruff check .

# Type check (pyright)
uv run pyright

# Tests (pytest)
uv run pytest -q
```

### Frontend (Node)

```sh
cd frontend

# Lint (ESLint)
npx eslint .

# Type check (tsc)
npx tsc --noEmit

# Production build
npm run build
```

CI is configured in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and runs on GitHub Actions.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Azure Environment (AEGIS-21)

Infrastructure-as-Code under [`infra/azure/`](infra/azure/) bootstraps the cloud environment:

- Resource group **`aegis-prod-rg`** in **West Europe**
- A **subscription-wide €30/month budget** with email alerts (80% / 100% actual, 100% forecast)
- **Contributor** role for the DevOps leads

| File | Purpose |
|------|---------|
| `infra/azure/main.bicep` | Resource group + cost budget (subscription scope) |
| `infra/azure/main.bicepparam` | Parameter values — **edit the alert emails here** |
| `infra/azure/provision.ps1` | Windows runner: deploy Bicep + assign roles |
| `infra/azure/provision.sh` | macOS/Linux runner (same steps) |

### Prerequisites

1. **Azure CLI** — https://aka.ms/installazurecli, then `az bicep install`
2. **Sign in**: `az login` (confirm the subscription with `az account show`)
3. **Owner** or **User Access Administrator** on the subscription is required to assign roles (a student subscription normally makes you Owner).

### Provision

```sh
cd infra/azure
# 1. Edit main.bicepparam — replace the REPLACE_WITH_*_EMAIL placeholders.
# 2. Edit the runner — set the subscription id + the Contributor emails.
# 3. Preview (no changes):
az deployment sub what-if --location westeurope \
  --template-file main.bicep --parameters main.bicepparam
# 4. Apply:  ./provision.ps1   (Windows)   |   ./provision.sh   (macOS/Linux)
```

### Verify

- **Resource group**: `az group show -n aegis-prod-rg`
- **Budget**: Azure Portal → *Cost Management → Budgets* → `aegis-monthly-budget` (€30 / Monthly)
- **Roles**: `az role assignment list --scope /subscriptions/<id> --query "[?roleDefinitionName=='Contributor'].principalName"`
- **Subscription ID** → record it in the team Google Doc (not in git — it's account metadata).

> **Notes:** budgets use the subscription's billing currency (adjust `budgetAmount` if it bills in USD). Re-running is idempotent — the resource group and budget are upserted by name.

### Cost estimate (AEGIS-63)

Rough **monthly** list-price estimate for the resources in `infra/main.bicep` (West Europe, EUR). Container Apps and Log Analytics are consumption-based, so actual cost depends on usage.

| Resource | SKU / size | Est. €/month |
|----------|-----------|-------------:|
| Container Registry | Basic | ~€4 |
| PostgreSQL Flexible Server | Standard_B1ms (1 vCore, Burstable) + 32 GiB | ~€14 |
| Service Bus | Standard namespace | ~€9 |
| Storage account | Standard_LRS (low usage) | ~€1 |
| Container Apps | backend 0.5 vCPU/1 GiB + frontend 0.25 vCPU/0.5 GiB, min-replicas 1 (after the monthly free grant) | ~€15 |
| Log Analytics workspace | PerGB2018, low ingest | ~€3 |
| **Total** | | **~€46 / month** |

✅ Within the ticket's **≤ €50/month** target — but it **crosses the AEGIS-21 €30 budget alert**, so either bump the budget to ~€60 or treat the alert as an early warning (student credits cover this short-term).

**Levers to trim toward €30:** Container Apps min-replicas 0 (scale-to-zero, cold start on first request) · Service Bus Basic instead of Standard (no topics/sessions — fine if only the `aegis-events` queue is needed) · stop/deallocate Postgres when not demoing. Prices are indicative; use `az deployment group what-if` + the Azure Pricing Calculator for an exact quote.

### Secrets — Azure Key Vault (AEGIS-77)

Production secrets live in an Azure Key Vault (`infra/modules/keyVault.bicep`), **never in git**. The backend Container App reads them at runtime via its **system-assigned managed identity** — no secret values are baked into images or env files.

**Architecture:** Key Vault stores `database-url`, `jwt-secret`, `service-bus-connection-string`, `storage-connection-string`. The vault uses **access policies** (not RBAC): the deploying user gets secret management; the backend app's managed identity gets read-only. The Container App injects each secret as an env var via a `keyVaultUrl` secret reference.

**Setup (run once, in three phases — the secrets must exist before the app references them):**

```sh
# 1. Create the vault (wireKeyVaultSecrets stays false) — grants you + the
#    backend identity access. Pass your object id so you can write secrets.
az deployment group create -g aegis-prod-rg --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
      postgresAdminPassword='<strong>' \
      postgresLocation=northeurope \
      deployerObjectId="$(az ad signed-in-user show --query id -o tsv)"

# 2. Store the secrets (values come from the deployment outputs; JWT is generated).
VAULT=$(az deployment group show -g aegis-prod-rg -n main --query properties.outputs.keyVaultName.value -o tsv)
az keyvault secret set --vault-name "$VAULT" --name jwt-secret --value "$(openssl rand -hex 32)"
az keyvault secret set --vault-name "$VAULT" --name database-url --value "<databaseUrl output>"
az keyvault secret set --vault-name "$VAULT" --name service-bus-connection-string --value "<serviceBusConnectionString output>"
az keyvault secret set --vault-name "$VAULT" --name storage-connection-string --value "<storageConnectionString output>"

# 3. Re-deploy with wireKeyVaultSecrets=true so the backend app pulls them.
az deployment group create -g aegis-prod-rg --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
      postgresAdminPassword='<strong>' postgresLocation=northeurope \
      deployerObjectId="$(az ad signed-in-user show --query id -o tsv)" \
      wireKeyVaultSecrets=true
```

**Verify retrieval:** `az containerapp show -g aegis-prod-rg -n backend-app --query properties.template.containers[0].env` shows the env vars wired to `secretRef`s, and the revision is healthy (an unresolved Key Vault reference would fail it). `az keyvault secret list --vault-name "$VAULT" -o table` lists the stored secrets.

> **Notes:** real-image consumption of these env vars lands with AEGIS-66 (the apps run placeholder images until then). CI/CD GitHub secrets for the deploy pipeline are configured in the CI/CD ticket. gitleaks continues to guard against any secret reaching git.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Project Structure

```
AEGIS/
├── backend/                  # FastAPI REST API
│   ├── app/
│   │   ├── main.py           # Application entry point
│   │   ├── config.py         # Pydantic settings
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # API route handlers
│   │   └── services/         # Business logic
│   ├── alembic/              # Database migrations
│   ├── tests/                # pytest test suite
│   └── pyproject.toml
│
├── frontend/                 # React 18 + TypeScript exam shell
│   ├── src/
│   │   ├── pages/            # Route-level page components
│   │   ├── context/          # React context (Auth)
│   │   └── api/              # Axios API client
│   ├── env.example           # Environment variable template
│   └── package.json
│
├── infra/                    # Azure Bicep IaC
│   └── ...                   # Container Apps, PostgreSQL, Service Bus, Blob
│
├── docs/                     # Architecture diagrams, sprint notes
├── .github/workflows/        # GitHub Actions CI
└── docker-compose.yml        # Full-stack local development
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Roadmap

- [x] User authentication — register, login, JWT tokens
- [x] Professor exam and quiz creation
- [x] Student session tracking
- [x] GDPR consent gate with server-side enforcement
- [x] Answer submission API
- [x] CI pipeline (ruff · pyright · pytest · eslint · tsc)
- [x] Docker Compose full-stack development environment
- [ ] Browser telemetry SDK (tab visibility, paste, keystroke intervals, window focus)
- [ ] Signal scoring engine (0–1 confidence score)
- [ ] Integrity report dashboard for professors
- [ ] Azure Service Bus integration for async telemetry ingestion
- [ ] Azure Container Apps deployment via Bicep IaC
- [ ] Real-time cohort view during live exams

See [open issues](https://github.com/COMP47250-team-project/AEGIS/issues) for a full list of proposed features and known bugs.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b AEGIS-<ticket>/your-feature`
3. Commit your changes using [Conventional Commits](https://www.conventionalcommits.org): `git commit -m "feat: add telemetry SDK"`
4. Push to your branch: `git push origin AEGIS-<ticket>/your-feature`
5. Open a pull request against `main`

Before opening a PR, make sure all CI checks pass locally (see [Running Tests & CI Checks](#running-tests--ci-checks)).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the Apache License 2.0. See [`LICENSE`](LICENSE) for details.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Contact

COMP47250 Team Project — University College Dublin, MSc Computer Science, 2026

Project repository: [https://github.com/COMP47250-team-project/AEGIS](https://github.com/COMP47250-team-project/AEGIS)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Acknowledgments

* [FastAPI](https://fastapi.tiangolo.com/) — the async Python web framework powering the backend
* [Vite](https://vitejs.dev/) — lightning-fast frontend build tooling
* [Tailwind CSS](https://tailwindcss.com/) — utility-first CSS framework
* [Alembic](https://alembic.sqlalchemy.org/) — database schema migrations
* [othneildrew/Best-README-Template](https://github.com/othneildrew/Best-README-Template) — README structure

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<!-- MARKDOWN REFERENCE LINKS & BADGES -->

[contributors-shield]: https://img.shields.io/github/contributors/COMP47250-team-project/AEGIS.svg?style=for-the-badge
[contributors-url]: https://github.com/COMP47250-team-project/AEGIS/graphs/contributors

[forks-shield]: https://img.shields.io/github/forks/COMP47250-team-project/AEGIS.svg?style=for-the-badge
[forks-url]: https://github.com/COMP47250-team-project/AEGIS/network/members

[stars-shield]: https://img.shields.io/github/stars/COMP47250-team-project/AEGIS.svg?style=for-the-badge
[stars-url]: https://github.com/COMP47250-team-project/AEGIS/stargazers

[issues-shield]: https://img.shields.io/github/issues/COMP47250-team-project/AEGIS.svg?style=for-the-badge
[issues-url]: https://github.com/COMP47250-team-project/AEGIS/issues

[license-shield]: https://img.shields.io/github/license/COMP47250-team-project/AEGIS.svg?style=for-the-badge
[license-url]: https://github.com/COMP47250-team-project/AEGIS/blob/main/LICENSE

[ci-shield]: https://github.com/COMP47250-team-project/AEGIS/actions/workflows/ci.yml/badge.svg?branch=main
[ci-url]: https://github.com/COMP47250-team-project/AEGIS/actions/workflows/ci.yml

[fastapi-badge]: https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi
[fastapi-url]: https://fastapi.tiangolo.com/

[python-badge]: https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org/

[react-badge]: https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[react-url]: https://react.dev/

[typescript-badge]: https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white
[typescript-url]: https://www.typescriptlang.org/

[vite-badge]: https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white
[vite-url]: https://vitejs.dev/

[tailwind-badge]: https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white
[tailwind-url]: https://tailwindcss.com/

[postgres-badge]: https://img.shields.io/badge/PostgreSQL_16-316192?style=for-the-badge&logo=postgresql&logoColor=white
[postgres-url]: https://www.postgresql.org/

[docker-badge]: https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white
[docker-url]: https://www.docker.com/

[azure-badge]: https://img.shields.io/badge/Azure-0089D6?style=for-the-badge&logo=microsoft-azure&logoColor=white
[azure-url]: https://azure.microsoft.com/
