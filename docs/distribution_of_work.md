# AEGIS - Distribution of Work

**Module:** COMP47250 Team Software Project (Microsoft partnership, 2026)   
**Project:** AEGIS — Adaptive Exam Guardian and Integrity System   
**Repository:** https://github.com/comp47250-team-project/aegis   
**Jira:** https://comp47250-ucd.atlassian.net (project key `AEGIS`)   
**Document owner:** Vijeth Prashanth Hegde (team lead)   
**Team size:** 6 members

---

## 1. Purpose

This document records each team member's specific contributions to AEGIS for the final submission. It is
intended to be **honest and independently verifiable** against the GitHub commit history and the Jira board.
Every row in the contribution table below can be reproduced from `git log` and cross-checked against the
linked Jira tickets and pull requests.


## 2. How to verify (methodology)

All figures in this document come from the repository's own history. To reproduce them:

```bash
# Commit counts per author name (raw – includes merge commits and split identities)
git log --format="%an" | sort | uniq -c | sort -rn

# Commit counts per author name+email (used to consolidate split identities)
git log --format="%an <%ae>" | sort | uniq -c | sort -rn

# A given member's authored feature commits (example)
git log --no-merges --author="jeevikabt27" --format="%h %ad %s" --date=short

# Pull requests merged into main
git log --merges --format="%h | %an | %s"
```

**Reporting basis.** The "Commits" column counts **non-merge authored commits** on `main` (the fairest proxy
for code authored, excluding integration/merge commits). Merge commits and the two Dependabot commits are
excluded from per-member counts. Percentages are **holistic**: they start from the commit counts but
are lightly adjusted for the scope, complexity and test-coverage of each member's work, plus non-code
contributions (code review, architecture, agile ceremonies, documentation). Raw commit counts are shown
alongside so the adjustment is transparent.


## 3. Raw GitHub evidence (`git log --format="%an" | sort | uniq -c | sort -rn`)

**Identity consolidation.** Several members committed under more than one Git identity (personal email vs.
GitHub `noreply`, and two members are both named *Tejas*). The mapping below is derived from the commit
email addresses and the files each identity touched, and is used throughout this document:

| Member | Git identities (name / email) |
| --- | --- |
| Vijeth Prashanth Hegde | `Vijeth P H <vijeth.ph@outlook.com>`, `vijethph <vijeth.ph@outlook.com>` |
| Raushan Nerkar | `Raushan Nerkar <…raushannerkar…>`, `raushannerkar <raushannerkar17@gmail.com>` |
| Tejas Tholakalabavi Dinesh | `tejas.tholakalabavi@gmail.com`, `tejas@Tejass-MacBook-Air.local`, `Tejas <…tejas-td…>` |
| Tejas Pantharapalya Venkatesh | `Tejas1107 <tejas6404@gmail.com>`, `Tejas1107 <…67309910+Tejas1107…>` |
| Jeevika Bangalore Thanuj Kumar | `jeevikabt27 <jeevikabt27@gmail.com>` |
| Lakshmi Kiran C M | `Lakshmi Kiran C M <…lakshmikirancm…>`, `lakshmikirancm <lakshmikirancm08@gmail.com>` |

> Note: the two Dependabot commits are automated dependency bumps and are not attributed to any member.


## 4. Contribution summary table

| Member | Primary areas owned | Key PRs / commits (Jira) | Commits* | Approx. % |
| --- | --- | --- | --- | --- |
| **Vijeth Prashanth Hegde** *(team lead)* | Backend architecture, WebSocket gateway, telemetry persistence, exam/quiz APIs, deployment config, E2E tests | #2 (AEGIS-33/34), #16 (AEGIS-35/38), #38 (AEGIS-48), #46 (AEGIS-49), #53/#71/#73 (AEGIS-65), #76 (AEGIS-110), #84 (AEGIS-109) | 18 | 20% |
| **Raushan Nerkar** | Azure infrastructure & IaC, CI/CD deployment, professor live-monitoring UI, super-admin console, manual grading & result-release | #40 (AEGIS-21), #48 (AEGIS-63), #50 (AEGIS-77), #52 (AEGIS-66), #42/#43 (AEGIS-58/59), #78–85 (AEGIS-112), #87/#90/#92 (AEGIS-107), #93 (AEGIS-74) | 21 | 20% |
| **Tejas Tholakalabavi Dinesh** | Student exam shell & auth UI, countdown/auto-submit, submit confirmation, event-timeline/history view, warning banners, quiz LRU cache | #7 (AEGIS-29), #18 (AEGIS-37), #27 (AEGIS-40), #41 (AEGIS-41), #64 (AEGIS-60), #70 (AEGIS-85), #80 (AEGIS-87), #88 (AEGIS-108) | 14 | 16% |
| **Lakshmi Kiran C M** | JWT auth endpoints, RBAC, signal-scoring components, professor exam-create form, scoring presets, signal-breakdown chart, student groups, backend test suite | #15 (AEGIS-26), #30 (AEGIS-27), #39 (AEGIS-54), #45 (AEGIS-56), #49 (AEGIS-62), #65 (AEGIS-68), #66 (AEGIS-84), #68 (AEGIS-86), #81 (AEGIS-105) | 13 | 16% |
| **Jeevika Bangalore Thanuj Kumar** | Telemetry SDK core, keystroke/IKI signal detectors, pure signal-scorer engine, baseline calculator, TypeScript strict-mode, pre-commit tooling | #8 (AEGIS-23), #21 (AEGIS-42), #32 (AEGIS-45), #44 (AEGIS-52), #54 (AEGIS-53), #55 (AEGIS-55), #56 (AEGIS-69), #77 (AEGIS-88) | 11 | 15% |
| **Tejas Pantharapalya Venkatesh** | Database schema & SQLAlchemy ORM, Alembic migrations, seed data, risk-score/alert triggers, CSV export API, architecture decision record | #5/#9 (AEGIS-30), #22 (AEGIS-32), #47 (AEGIS-57), #51 (AEGIS-61), #89 (AEGIS-91) | 9 | 14% |
| **Total** | | | **86** | **100%** |

\* Non-merge authored commits on `main`, with split Git identities consolidated. Two Dependabot
commits are excluded, so member commits (86) + Dependabot (2) = 88 total non-merge commits.


## 5. Per-member narratives

### Vijeth Prashanth Hegde (team lead)
Vijeth set up the repository and established the **backend architecture and real-time pipeline**. He authored
the professor/quiz/exam routes (AEGIS-33/34), the answer-submission endpoint and GDPR consent screen
(AEGIS-35/38), the exam-shell question flow (AEGIS-39), the authenticated WebSocket gateway (AEGIS-48) and the
Service Bus telemetry-persistence path (AEGIS-49) - the spine that keeps telemetry independent of exam
submission. He also drove deployment configuration (AEGIS-65), fixed a batch of multi-session bugs (AEGIS-110)
and added the Playwright E2E suite (AEGIS-109). As team lead he authored the CODEOWNERS map and `AGENTS.md`,
reviewed and merged teammates' PRs, and coordinated sprint planning on Jira. His key architectural decision was
enforcing that monitoring failures can never block a student's submission.

### Raushan Nerkar
Raushan owned the **cloud and deployment backbone** of AEGIS. He authored the Azure Infrastructure-as-Code
(AEGIS-21 resource group/budget/RBAC, AEGIS-63 full Bicep environment), the Key Vault + managed-identity
secret wiring (AEGIS-77), and the ACR image deployment pipeline (AEGIS-66), including the CD role-assignment
fixes that unblocked rollout. On the product side he built the **professor live-monitoring experience** — the
active-session dashboard (AEGIS-58) and the real-time student card grid with risk scores (AEGIS-59) — and later
the super-admin console (AEGIS-107), the manual grading + conditional result-visibility workflow (AEGIS-112),
question-bank import (AEGIS-90) and the health-check endpoint (AEGIS-89). A key decision he drove was consuming
secrets exclusively from Key Vault via managed identity rather than baking them into images.


### Tejas Tholakalabavi Dinesh
Tejas TD owned most of the **student-facing exam experience**. He authored the login/register pages with the
JWT auth context (AEGIS-29), the student dashboard (AEGIS-37), the countdown timer with T-30s warning and
auto-submit (AEGIS-40), the post-submission confirmation page (AEGIS-41) and the non-blocking warning banners
(AEGIS-85). He built the event-timeline "load more" and history view with a 1000-event cap (AEGIS-60),
implemented bulk CSV enrolment on the frontend (AEGIS-87), and added the quiz LRU cache to cut repeated DB hits
(AEGIS-108). His work concentrated in `frontend/src/pages` and `frontend/src/components`. A notable learning was
using ref-based state to avoid stale-closure bugs during auto-submit (a fix he made in AEGIS-40).

### Lakshmi Kiran C M
Lakshmi contributed across **authentication and the signal-scoring layer**. She authored the JWT auth endpoints
(AEGIS-26) and the `require_role` RBAC dependency (AEGIS-27), then built several backend scoring components:
tab-blur/paste scorers (AEGIS-54) and the first-keypress/answer-time/resize scorers (AEGIS-56), plus the
tab-blur/return detection (AEGIS-43). She added the scoring sensitivity presets (strict/standard/lenient,
AEGIS-84), the signal-breakdown chart on the professor detail panel (AEGIS-86), the professor create-exam form
(AEGIS-62) and student groups/cohorts (AEGIS-105). She also strengthened the backend test suite and auth
fixtures (AEGIS-68). Her footprint is heaviest in `backend/tests` and `backend/app/services`, reflecting a
test-first approach to the scoring rules.

### Jeevika Bangalore Thanuj Kumar
Jeevika owned the **telemetry SDK core and the pure scoring engine** — the most algorithmically involved,
test-heavy modules. She scaffolded the SDK with the CircularBuffer/offline queue (AEGIS-42), authored the
keystroke IKI signal detector (AEGIS-45) and unit tests for the first-keypress/resize signals (AEGIS-46), then
built the pure signal-scorer engine (AEGIS-52, 14 unit tests), the baseline calculator (AEGIS-53, 15 unit tests)
and the IKI outlier scorer with Z-score windowing (AEGIS-55). She also set up pre-commit hooks (AEGIS-23) and
drove TypeScript strict-mode compliance (AEGIS-69), and fixed the countdown timer start behaviour (AEGIS-88).
Although her commit count is lower, each commit delivered a self-contained, thoroughly tested module. Her key
decision was keeping the scorers as pure functions to make them deterministic and unit-testable.

### Tejas Pantharapalya Venkatesh
Tejas PV built the **data foundation** everything else depends on. He authored the initial SQLAlchemy ORM and
database wiring (AEGIS-30), the environment/database/config setup, and the seed script for users, professors,
enrolments and quizzes (AEGIS-32). He then implemented the risk-score and alert-flag triggers that fire when the
confidence threshold is exceeded (AEGIS-57), the CSV export API with integration tests (AEGIS-61), and authored
the architecture decision record `DECISIONS.md` (AEGIS-91). His work centres on `backend/app/models`,
`backend/app/database.py` and the migration/seed tooling. A key contribution was establishing the schema and
seed data early so the rest of the team could develop and test against realistic data.

