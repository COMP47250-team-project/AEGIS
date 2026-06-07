# Contributing to AEGIS

Welcome! This document is the single source of truth for how the team works together on the codebase.

---

## Table of Contents

1. [Quick Start (local setup)](#1-quick-start)
2. [Branching strategy](#2-branching-strategy)
3. [Commit message convention](#3-commit-message-convention)
4. [Pull request process](#4-pull-request-process)
5. [Code review checklist](#5-code-review-checklist)
6. [Directory responsibilities](#6-directory-responsibilities)

---

## 1. Quick Start

### Prerequisites
- Python 3.12+
- Node.js 22+
- Docker Desktop
- Azure CLI (for deployment)

### Run locally

```bash
# Clone the repo
git clone https://github.com/<org>/AEGIS.git
cd AEGIS

# Copy environment variables
cp .env.example .env
# Edit .env and fill in any required values

# Start everything with Docker Compose
docker compose up --build

# Backend API:  http://localhost:8000
# Frontend:     http://localhost:5173
# API docs:     http://localhost:8000/docs
```

### Backend only (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload
```

### Frontend only (without Docker)

```bash
cd frontend
npm install
npm run dev
```

---

## 2. Branching Strategy

We use **GitHub Flow** — one long-lived branch (`main`) with short-lived feature branches.

### Branch naming

```
feature/AEGIS-XXX-short-slug     # new feature
fix/AEGIS-XXX-what-is-fixed      # bug fix
chore/AEGIS-XXX-what-is-done     # config, docs, tooling
```

**Examples:**
```
feature/AEGIS-27-jwt-auth
fix/AEGIS-49-websocket-reconnect
chore/AEGIS-18-contributing-guide
```

### Rules
- **Never push directly to `main`** — always open a PR
- Branch off from the latest `main`:
  ```bash
  git checkout main && git pull
  git checkout -b feature/AEGIS-XXX-slug
  ```
- Keep branches short-lived (≤ 2 days). If your branch lives longer, rebase frequently.
- Delete the branch after merge.

---

## 3. Commit Message Convention

We follow **Conventional Commits** (subset):

```
<type>(AEGIS-XXX): <short imperative description>

[optional body — what and why, not how]
```

### Types

| Type       | Use for |
|------------|---------|
| `feat`     | New feature visible to a user |
| `fix`      | Bug fix |
| `test`     | Tests only |
| `refactor` | Code change that is not feat or fix |
| `chore`    | Build, CI, config, tooling |
| `docs`     | Documentation only |

### Examples

```
feat(AEGIS-48): add JWT auth handshake to WebSocket gateway
fix(AEGIS-55): clamp IKI z-score to prevent negative sigmoid input
test(AEGIS-68): add 15 pytest cases for scoring pipeline
chore(AEGIS-12): scaffold monorepo directory structure
docs(AEGIS-20): add architecture diagrams to docs/
```

### Rules
- Subject line ≤ 72 characters
- Imperative mood ("add", not "added" or "adds")
- Reference the Jira ticket in every commit

---

## 4. Pull Request Process

### Opening a PR

1. Push your branch and open a PR against `main`.
2. Use the **PR template** (pre-filled automatically — see `.github/PULL_REQUEST_TEMPLATE.md`).
3. Link the Jira ticket in the PR description.
4. Assign at least one reviewer (see [Directory responsibilities](#6-directory-responsibilities)).
5. Ensure all CI checks pass before requesting review.

### Merge requirements

- **≥ 1 approval** from a team member (backend PRs → M1 or M4 must approve)
- **All CI checks green** (lint, type-check, tests, build)
- **No unresolved review comments**
- Use **Squash and Merge** to keep `main` history clean

### Review turnaround

Reviewers aim to respond within **2 hours** during sprint hours (9am–midnight Dublin time).

---

## 5. Code Review Checklist

When reviewing a PR, check:

**For all PRs:**
- [ ] Does the code match the Jira acceptance criteria?
- [ ] Are there no secrets or credentials committed?
- [ ] Does the PR update tests for changed logic?

**For backend PRs:**
- [ ] Pydantic models used at API boundaries (no raw dicts returned)
- [ ] All DB queries use async ORM (no synchronous `session.execute`)
- [ ] New endpoints protected with `Depends(get_current_user_id)` unless explicitly public
- [ ] No raw SQL strings (SQLAlchemy Core or ORM only)

**For frontend PRs:**
- [ ] TypeScript strict mode — no `any` types
- [ ] No secrets or API keys in frontend code
- [ ] Components import from `@/` alias, not relative `../../`

**For infra PRs:**
- [ ] Secrets passed via `@secure()` parameter — never hardcoded
- [ ] Resource names follow `${prefix}-resource` convention
- [ ] `what-if` run output reviewed before merging

---

## 6. Directory Responsibilities

| Directory               | Owner(s)                    |
|-------------------------|-----------------------------|
| `backend/`              | M1 (Vijeth) + M4            |
| `backend/alembic/`      | M4 (DB lead)                |
| `backend/app/scoring/`  | M2 (Signal Scorer)          |
| `frontend/`             | M6                          |
| `infra/`                | M5 (DevOps)                 |
| `.github/workflows/`    | M5 (DevOps)                 |
| `docs/`                 | All (open contribution)     |

CODEOWNERS automatically requests the correct reviewer when a PR touches these paths.
