<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Apache License][license-shield]][license-url]
[![CI][ci-shield]][ci-url]
[![CD][cd-shield]][cd-url]
[![Secret scanning][gitleaks-shield]][gitleaks-url]
[![Known Vulnerabilities](https://snyk.io/test/github/COMP47250-team-project/AEGIS/badge.svg)](https://snyk.io/test/github/COMP47250-team-project/AEGIS)
[![Quality gate status](https://sonarcloud.io/api/project_badges/measure?project=COMP47250-team-project_aegis&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=COMP47250-team-project_aegis&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=COMP47250-team-project_aegis&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)
[![Technical Debt](https://sonarcloud.io/api/project_badges/measure?project=COMP47250-team-project_aegis&metric=sqale_index)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=COMP47250-team-project_aegis&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)
[![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-dark.svg)](https://sonarcloud.io/summary/new_code?id=COMP47250-team-project_aegis)


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/COMP47250-team-project/AEGIS">
    <img src="docs/images/aegis-logo.png" alt="AEGIS logo" width="96" height="96">
  </a>

  <h3 align="center">AEGIS</h3>

  <p align="center">
    <strong>Adaptive Exam Guardian and Integrity System</strong>
    <br />
    <br />
    <a href="#about-the-project">Explore the docs »</a>
    <br />
    <a href="https://github.com/COMP47250-team-project/AEGIS/issues/new?labels=bug">Report Bug</a>
    &middot;
    <a href="https://github.com/COMP47250-team-project/AEGIS/issues/new?labels=enhancement">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
        <li><a href="#architecture">Architecture</a></li>
        <li><a href="#integrity-scoring">Integrity Scoring</a></li>
        <li><a href="#privacy-posture">Privacy Posture</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#configuration">Configuration</a></li>
      </ul>
    </li>
    <li>
      <a href="#usage">Usage</a>
      <ul>
        <li><a href="#make-targets">Make Targets</a></li>
        <li><a href="#api-surface">API Surface</a></li>
        <li><a href="#tests">Tests</a></li>
        <li><a href="#deployment">Deployment</a></li>
      </ul>
    </li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

Remote proctoring normally means a webcam, an installed agent, and an algorithm deciding whether a student looks guilty. AEGIS drops all three. It runs in a plain browser tab and records only metadata about how the exam was produced: focus loss, paste length, keystroke spacing, answer timing, window resizes.

Six of those signals combine into one score between 0 and 1. The professor reads the score, opens the event timeline behind it, and decides. The system issues no misconduct verdict on its own.

What it ships with:

* Quiz authoring with a question bank, exam scheduling per course, and a per-exam scoring preset.
* Enrolment by roster pick, pasted email list, or saved student group.
* Open-book mode with an allowlisted PDF and link panel, each access timed.
* Live monitor pushing per-student risk over a WebSocket every 5 seconds.
* Post-exam signal breakdown, event timeline, and CSV export.
* Short-answer grading with staged release, plus an optional AI copilot for integrity briefs, grade suggestions, and answer-similarity collusion detection.

Screenshots are present in [screenshots.md](docs/screenshots.md) file.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

[![FastAPI][fastapi-badge]][fastapi-url]
[![Python][python-badge]][python-url]
[![React][react-badge]][react-url]
[![TypeScript][ts-badge]][ts-url]
[![Vite][vite-badge]][vite-url]
[![Tailwind CSS][tailwind-badge]][tailwind-url]
[![PostgreSQL][postgres-badge]][postgres-url]
[![Docker][docker-badge]][docker-url]
[![Kubernetes][k8s-badge]][k8s-url]
[![Helm][helm-badge]][helm-url]
[![Bicep][bicep-badge]][bicep-url]
[![Azure][azure-badge]][azure-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Architecture

[![AEGIS architecture][product-screenshot]](#architecture)

Telemetry and answers travel on separate paths. That is the load-bearing decision: if the WebSocket dies, the student keeps answering and submitting, and only monitoring degrades.

The browser SDK batches events into a bounded ring buffer and reconnects with exponential backoff. Under sustained failure it drops the oldest events, because an incomplete telemetry stream is acceptable and a stalled exam is not.

Service Bus decouples ingestion from scoring. With no connection string set, the same events are scored in-process, so a local stack behaves identically without Azure. The AI client resolves Azure OpenAI, then a local Ollama endpoint, then a labelled stub, so every copilot feature degrades cleanly with zero credentials.

Live and final scores are computed differently on purpose. The live monitor reads in-memory counters, so 100 concurrent students cost no queries per tick, which makes it an estimate. At exam close the session is rescored from stored events against the student's own typing baseline, and that number is what reports show.

Persistence is 18 tables over 17 Alembic migrations: users, courses, quizzes, questions, exam sessions, enrolments, answers, telemetry events, typing baselines, session scores, risk flags, groups, open-book resources and access records, an append-only audit log, and password reset tokens.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Integrity Scoring

Six components, each normalised to 0.0–1.0, combined as a weighted sum. Weights stay server-side so the frontend never exposes the rules.

| Signal | Measures | Standard weight |
| --- | --- | --- |
| Tab switching | Focus and visibility loss, weighted by time away | 0.30 |
| Paste | Paste events and pasted length | 0.25 |
| Keystroke intervals | Outliers against the student's own rhythm | 0.20 |
| First keypress delay | Silence between question load and first key | 0.10 |
| Answer time | Answers finished implausibly fast for their length | 0.10 |
| Window resize | Resizes consistent with tiling beside another window | 0.05 |

Professors pick one preset per exam. Lenient exists for open-book research exams where multi-tab work is expected; strict is for closed-book conditions.

| Preset | Tab | Paste | Keystrokes | First keypress | Answer time | Resize |
| --- | --- | --- | --- | --- | --- | --- |
| Strict | 0.35 | 0.30 | 0.20 | 0.07 | 0.05 | 0.03 |
| Standard | 0.30 | 0.25 | 0.20 | 0.10 | 0.10 | 0.05 |
| Lenient | 0.15 | 0.20 | 0.25 | 0.15 | 0.20 | 0.05 |

Two thresholds: crossing 0.70 mid-exam raises a risk flag and alerts the live monitor; reporting treats 0.40 and above as flagged for review, deliberately lower so borderline sessions reach a human instead of being filtered out.

No single signal can flag a session. Maxing out tab switching alone yields 0.30 under the standard preset, below the review threshold. Reaching it requires two or more signals agreeing.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Privacy Posture

* No webcam, microphone, screen recording, or browser extension.
* Keystroke timing only. Key values are never transmitted or stored.
* Paste events record length and target field, never clipboard contents.
* Questions are withheld until consent is recorded. The check is server-side and returns 403 while consent is null, so it cannot be bypassed from the client.
* No automated decision-making. A human makes every call, and students see their own score.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

Docker Compose is the fastest path to a working stack. The manual path is better for a tight edit-reload loop on one service.

### Prerequisites

Compose path:

* Docker and Docker Compose
  ```sh
  docker compose version
  ```

Manual path, additionally:

* Python 3.12 with [uv](https://docs.astral.sh/uv/)
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
* Node 20
  ```sh
  node --version
  ```
* PostgreSQL 16
  ```sh
  psql --version
  ```

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/COMP47250-team-project/AEGIS.git
   cd AEGIS
   ```
2. Copy the environment file. Defaults work as-is for local development.
   ```sh
   cp .env.example .env
   ```
3. Build and start the stack, then load demo data. `make seed` prints the credentials it creates.
   ```sh
   make up
   make seed
   ```
4. Open the app. Stop with `make down`, or `make down-v` to drop the volumes.

   | Service | Address |
   | --- | --- |
   | Frontend | http://localhost:5173 |
   | Backend | http://localhost:8000 |
   | Swagger UI | http://localhost:8000/docs |
   | ReDoc | http://localhost:8000/redoc |
   | PostgreSQL | localhost:5432 |
   | Azurite blob | http://localhost:10000 |

5. Optional, run the AI copilot against a local model instead of Azure OpenAI, then set `OLLAMA_BASE_URL=http://ollama:11434/v1` in `.env` and restart the backend.
   ```sh
   docker compose --profile ai up -d ollama
   docker exec -it aegis-ollama-1 ollama pull qwen3:8b
   docker exec -it aegis-ollama-1 ollama pull nomic-embed-text
   ```

<details>
  <summary>Manual setup without Docker</summary>

```sh
# 1. Database
createdb aegis
psql -c "CREATE USER aegis WITH PASSWORD 'aegis_dev_pw'; ALTER DATABASE aegis OWNER TO aegis;"

# 2. Backend
cd backend
uv sync
export DATABASE_URL="postgresql+asyncpg://aegis:aegis_dev_pw@localhost:5432/aegis"
export DATABASE_URL_SYNC="postgresql://aegis:aegis_dev_pw@localhost:5432/aegis"
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Frontend, second terminal
cd frontend
cp env.example .env
npm install
npm run dev
```

On Windows PowerShell, replace `export FOO=bar` with `$env:FOO = "bar"`.
</details>

### Configuration

Secrets are read from the environment only. Nothing is hardcoded, and gitleaks runs as a pre-commit hook to keep it that way. Replace `JWT_SECRET_KEY` before anything leaves your machine.

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://aegis:aegis_dev_pw@localhost:5432/aegis` | Async driver, used by the app |
| `DATABASE_URL_SYNC` | `postgresql://aegis:aegis_dev_pw@localhost:5432/aegis` | Sync driver, used by Alembic |
| `JWT_SECRET_KEY` | placeholder | Replace: `openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `APP_ENV` | `development` | |
| `LOG_LEVEL` | `DEBUG` | |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated. Any `*.azurecontainerapps.io` origin is additionally allowed by regex |
| `VITE_API_URL` | `http://localhost:8000` | Frontend. WebSocket URL is derived by swapping the scheme |

Azure services are all optional, and each has a local fallback.

| Variable | Default | Behaviour when unset |
| --- | --- | --- |
| `AZURE_SERVICE_BUS_CONNECTION_STRING` | unset | Telemetry scored in-process instead of via a queue |
| `AZURE_SERVICE_BUS_QUEUE_NAME` | `telemetry-events` | |
| `SCORE_QUEUE_NAME` | `score-jobs` | |
| `AZURE_STORAGE_CONNECTION_STRING` | unset | Compose points this at Azurite |
| `AZURE_STORAGE_CONTAINER_NAME` | `exam-resources` | Open-book PDF uploads |
| `ACS_CONNECTION_STRING` | unset | Password reset emails printed to stdout |
| `ACS_SENDER_ADDRESS` | unset | Verified Communication Services sender |
| `FRONTEND_BASE_URL` | `http://localhost:5173` | Builds reset links |

AI copilot. With no provider configured it returns clearly labelled stub output, so the UI stays testable without credentials.

| Variable | Default | Notes |
| --- | --- | --- |
| `AI_FEATURES_ENABLED` | `true` | Set false to hide the copilot |
| `AZURE_OPENAI_ENDPOINT` | unset | First choice provider |
| `AZURE_OPENAI_API_KEY` | unset | |
| `AZURE_OPENAI_API_VERSION` | `2025-01-01-preview` | |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4.1` | |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | `text-embedding-3-small` | Collusion detection embeddings |
| `OLLAMA_BASE_URL` | unset | Second choice, OpenAI-compatible `/v1` endpoint |
| `OLLAMA_CHAT_MODEL` | `qwen3:8b` | |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Usage

After `make seed`, sign in as the seeded professor and walk the loop:

1. Build a quiz, or import questions from a published one.
2. Schedule it against a course with a start time, duration, and scoring preset. Turn on open-book mode to attach allowlisted PDFs and links.
3. Enrol students individually, by pasted email list, or by student group.
4. Open the exam. Students consent, then sit it. Monitored actions surface a banner and never block them.
5. Watch the live monitor while it runs, then close the exam.
6. Read the signal breakdown per student, grade short answers, release results, and export CSV.

Sign in as a seeded student in a second browser profile to drive the other side.

### Make Targets

`make help` prints the generated list. The four groups:

| Group | Targets |
| --- | --- |
| Docker Compose | `up`, `down`, `down-v`, `build`, `logs`, `ps`, `restart`, `shell`, `seed` |
| Kubernetes (minikube) | `cluster-up`, `images`, `deploy`, `k8s-seed`, `k8s-status`, `k8s-logs`, `k8s-shell`, `url`, `expose`, `unexpose`, `diagnose`, `tunnel`, `tunnel-stop` |
| Tests and verification | `test`, `e2e`, `lint`, `smoke` |
| Teardown | `undeploy`, `clean`, `cluster-down`, `cluster-delete`, `nuke` |

Service-scoped targets take `SVC=`, for example `make logs SVC=frontend`. The Helm chart can be exercised on minikube, which is closer to the deployed topology than Compose:

```sh
make cluster-up   # start minikube, enable ingress
make images       # build both images into the cluster
make deploy       # helm install, stamping the live cluster IP into ingress hosts and CORS
make k8s-seed     # create blob containers, load demo data
make url          # print the app and api URLs
```

`make expose` port-forwards the ingress when the minikube IP is not routable from the host, and `make diagnose` explains why the URLs are unreachable when they are.

### API Surface

71 REST routes and 2 WebSocket endpoints across 14 routers. Interactive docs are generated at `/docs` and `/redoc` on any running instance.

| Area | Prefix | Covers |
| --- | --- | --- |
| Auth | `/auth` | Register, login, refresh, logout, forgot and reset password |
| Admin | `/admin` | Super-admin users, exams, audit log |
| Courses | `/courses` | Courses and enrolled students |
| Quizzes | `/quizzes` | Quiz and question authoring, question bank import |
| Exams | `/exams` | Scheduling, state transitions, enrolment, answers, grading, release |
| Resources | `/exams/{id}/resources` | Open-book uploads, links, access tracking |
| Groups | `/groups` | Student groups and bulk enrolment |
| Student | `/student` | Dashboard, exam list, results |
| Users | `/users` | Roster lookups |
| Sessions | `/sessions` | Session scores, signal breakdowns, event timelines |
| Export | `/api/sessions/{exam_id}/export` | Streaming CSV of scores, flags, event counts |
| AI | `/ai` | Integrity brief, grade suggestions, collusion detection |
| Health | `/healthz`, `/api/health` | Liveness, and per-subsystem checks for database, Service Bus, blob |
| WebSocket | `/ws/exam/{id}`, `/ws/professor/{id}` | Student telemetry upstream, professor snapshots downstream |

### Tests

```sh
make test     # 370 backend tests across 40 files
make lint     # ruff on backend, eslint on frontend
make e2e      # Playwright against a live compose stack
```

Backend tests run on in-memory SQLite, so they need no database and no Docker. The scoring engine is pure with no I/O, which is what makes each of the six components testable in isolation. Frontend unit tests are 79 vitest cases across 12 files (`cd frontend && npm run test`), and types are checked with `uv run pyright` and `npm run build`.

The end-to-end spec drives the loop that matters: a professor creates and opens an exam, a student consents, sits it, triggers monitored behaviour and submits, then the professor reads the resulting integrity report.

Install the hooks once and they run on every commit (gitleaks, ruff lint and format, whitespace and merge-conflict checks):

```sh
uv tool install pre-commit
pre-commit install
```

Measured results, with sample sizes stated because they are small:

* **Detection:** 10 controlled sessions, 5 honest and 5 simulated AI-assisted, standard preset at the 0.40 threshold: precision 1.00, recall 1.00, FPR 0.00, AUC-ROC 1.00. Honest scores 0.06–0.175, assisted 0.438–0.641, nothing near the boundary. This shows the pipeline works end to end, not that it is accurate at scale.
* **Load:** k6 at 50 concurrent WebSocket students: 100% connection success, answer p99 390–545 ms. At 100: 100% connection success, p99 686–952 ms, which misses the 800 ms target at the top end. Backend memory held at 172–173 MiB, so the ceiling is request handling rather than telemetry.
* **Usability:** SUS mean 92.86 over 7 participants, grade A.

### Deployment

Two independent tracks share one container registry. Both are infrastructure-as-code; neither needs portal work.

| Track | Defined in | Driven by |
| --- | --- | --- |
| Azure Container Apps (primary) | `infra/main.bicep` | `infra.yml` provisions, `cd.yml` builds, pushes, deploys, smoke-tests |
| AKS with Helm | `infra/aks/`, `helm/aegis/` | `deploy-aks.yml` on manual dispatch |

The Bicep stack provisions a container registry, a Container Apps environment wired to Log Analytics, PostgreSQL Flexible Server, Service Bus, Blob Storage, Communication Services, Key Vault, and a budget with email alerts, then deploys backend and frontend as Container Apps. Azure login uses OIDC federated credentials, so no long-lived service principal secret is stored in GitHub. CD curls `/healthz` and `/health` before reporting green.

On the AKS track, ingress routes two hostnames rather than paths, one to the frontend and one to the backend, because the backend mounts routers at the root and the SPA owns client-side routes such as `/student` and `/admin`. That track's backend secret is created by the workflow from GitHub secrets; Key Vault and managed identity apply to the Container Apps track only. The `k8s/` Kustomize tree describes the same topology and is kept for reference, while the Helm chart is what the Makefile and workflows deploy.

The project's own Azure environment is being decommissioned at the end of the module, so no live URLs are listed here. Everything needed to stand up a fresh environment is in `infra/`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- CONTRIBUTING -->
## Contributing

Work is tracked as Jira issues under the AEGIS project key, one branch and one pull request per issue.

1. Branch as `type/short-description`, for example `feat/collusion-threshold`.
2. Commit with Conventional Commits and the issue key: `feat(scoring): add lenient preset (AEGIS-84)`.
3. Run `make lint && make test` before pushing.
4. Open a pull request against `main`. CI runs backend lint, types and tests, frontend lint, types, unit tests and build, then Playwright against a live compose stack. Reviewers come from `CODEOWNERS`.

New behaviour needs a test. New telemetry needs a line in the student-facing consent notice, and a good reason.

### Contributors:

<a href="https://github.com/COMP47250-team-project/AEGIS/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=COMP47250-team-project/AEGIS" alt="contrib.rocks image" />
</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the Apache License 2.0. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Built by a six-person MSc Computer Science team at University College Dublin for COMP47250 Team Software Project, in partnership with Microsoft, 2026.

Project Link: [https://github.com/COMP47250-team-project/AEGIS](https://github.com/COMP47250-team-project/AEGIS)

Issue tracker: [AEGIS board on Jira](https://comp47250-ucd.atlassian.net/jira/software/projects/AEGIS/boards/1)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [UCD School of Computer Science](https://www.ucd.ie/cs/)
* Mentors from [Microsoft Ireland](https://www.microsoft.com/en-ie/aboutireland), for weekly architecture and Azure review
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
* [Img Shields](https://shields.io)
* [FastAPI](https://fastapi.tiangolo.com/) and [SQLAlchemy](https://www.sqlalchemy.org/)
* [Playwright](https://playwright.dev/) and [k6](https://k6.io/), for end-to-end and load testing
* [Ollama](https://ollama.com/), which made the AI features developable without cloud credentials
* [gitleaks](https://github.com/gitleaks/gitleaks) and [pre-commit](https://pre-commit.com/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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
[ci-shield]: https://img.shields.io/github/actions/workflow/status/COMP47250-team-project/AEGIS/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI
[ci-url]: https://github.com/COMP47250-team-project/AEGIS/actions/workflows/ci.yml
[cd-shield]: https://img.shields.io/github/actions/workflow/status/COMP47250-team-project/AEGIS/cd.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CD
[cd-url]: https://github.com/COMP47250-team-project/AEGIS/actions/workflows/cd.yml
[gitleaks-shield]: https://img.shields.io/badge/secret_scanning-gitleaks-4C4A73?style=for-the-badge&logo=git&logoColor=white
[gitleaks-url]: https://github.com/COMP47250-team-project/AEGIS/blob/main/.pre-commit-config.yaml
[product-screenshot]: docs/images/ArchitectureDiagram.png
[fastapi-badge]: https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white
[fastapi-url]: https://fastapi.tiangolo.com/
[python-badge]: https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white
[python-url]: https://www.python.org/
[react-badge]: https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[react-url]: https://react.dev/
[ts-badge]: https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white
[ts-url]: https://www.typescriptlang.org/
[vite-badge]: https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white
[vite-url]: https://vite.dev/
[tailwind-badge]: https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwindcss&logoColor=white
[tailwind-url]: https://tailwindcss.com/
[postgres-badge]: https://img.shields.io/badge/PostgreSQL_16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white
[postgres-url]: https://www.postgresql.org/
[docker-badge]: https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white
[docker-url]: https://www.docker.com/
[k8s-badge]: https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white
[k8s-url]: https://kubernetes.io/
[helm-badge]: https://img.shields.io/badge/Helm-0F1689?style=for-the-badge&logo=helm&logoColor=white
[helm-url]: https://helm.sh/
[bicep-badge]: https://img.shields.io/badge/Bicep-00A4EF?style=for-the-badge&logo=microsoftazure&logoColor=white
[bicep-url]: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
[azure-badge]: https://img.shields.io/badge/Azure-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white
[azure-url]: https://azure.microsoft.com/
