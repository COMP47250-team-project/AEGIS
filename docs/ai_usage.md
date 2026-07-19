# AEGIS - AI Usage Disclosure

**Module:** COMP47250 Team Software Project (Microsoft partnership, 2026)     
**Project:** AEGIS - Adaptive Exam Guardian and Integrity System     
**Repository:** https://github.com/comp47250-team-project/aegis    
**Document owner:** Vijeth Prashanth Hegde (team lead)    
**Team size:** 6 members

---

## 0. Statement of intent

The AEGIS team used AI coding assistants throughout development. This document discloses **which tools were
used, for what, and under what human oversight**, in the interest of academic integrity and in line with the
module's expectations on transparent AI use. Every governance claim below is backed by an artifact committed to
the repository (`AGENTS.md`, `CLAUDE.md`, `docs/DECISIONS.md`) so it can be
independently verified.

Our guiding principle throughout was simple and is enforceable: **no AI-generated code was merged unless the
responsible team member could explain every line of it.** AI was a productivity and learning aid, not a
substitute for understanding or for team decision-making.

---

## 1. Tools used

| Tool | Version / Plan | Primary use |
| --- | --- | --- |
| **Claude Code (Anthropic)** | Claude Opus 4.8 (CLI) | Architecture design, strategy/documentation drafting, code scaffolding, debugging, Jira ticket drafting |
| **GitHub Copilot** | Individual/Pro (in-IDE) | In-editor code completion, boilerplate (routers, models, Pydantic schemas, test fixtures), infrastructure-as-code (Bicep) |
| **ChatGPT (OpenAI)** | GPT-5.5 | Q&A, architecture brainstorming, debugging discussions, documentation drafts |
| **Atlassian Rovo MCP** | via Claude Code | Jira ticket creation, backlog queries, sprint bookkeeping (project `AEGIS`) |



**Verifiable in the repository:**
- `CLAUDE.md` and the `.claude/` working directory - Claude Code configuration and session state.
- `AGENTS.md` - a universal coding-agent operating contract, which names the full set of
  agent tools permitted to operate in the repo.
- The Atlassian Rovo MCP configuration block in `AGENTS.md` (project key, cloud ID, query limits).


## 2. What AI assisted with

AI tools were applied across the following areas. In every case a named team member owned, reviewed and
integrated the output:

- **Project scaffolding** - initial FastAPI application structure, Docker Compose local-dev stack, Alembic
  migration setup, and repository boilerplate.
- **Boilerplate & repetitive code** - Copilot completion for routers, SQLAlchemy models, Pydantic schemas, and
  test fixtures where the pattern was already established by a human.
- **Infrastructure-as-code** - assistance drafting Azure Bicep templates (Container Apps, PostgreSQL, Service
  Bus, ACR, Blob) and GitHub Actions CI/CD workflows.
- **Debugging** - reasoning through async SQLAlchemy patterns, WebSocket lifecycle issues, and CI/deployment
  failures.
- **Signal-scoring logic review** - sanity-checking edge cases in the six behavioural signal scorers and the
  baseline calculator (human-authored tests remained the source of truth for correctness).
- **Documentation drafting** - first drafts of strategy documents, architecture decision records
  (`docs/DECISIONS.md`), the interview-prep sheet, and this disclosure, all reviewed and edited by the team.
- **Privacy/consent wording** - drafting and refining the GDPR consent text shown before monitoring begins.
- **Project management** - drafting Jira tickets and organising the backlog via the Atlassian Rovo MCP
  integration (human-reviewed before creation).


## 3. Review and oversight process

AI use was governed by explicit, committed rules - not left to individual discretion:

1. **Human review of every integration**: All AI-generated code was reviewed by the team member who integrated
   it, and merged only through a pull request. Branch protection on `main` required **at least one peer
   approval** and a passing CI run (lint + type-check + tests) before merge.
2. **"Explain every line" rule**: *No AI-generated code merges without
   the responsible team member being able to explain every line.* This is the team's core integrity guarantee
   and applies regardless of how a piece of code was first drafted.
3. **Human-written tests verify AI-scaffolded code**: Correctness was established by tests written and owned by
   team members (e.g. the pure signal-scorer engine and baseline calculator each ship with human-authored unit
   tests). AI was not trusted to self-certify its own output.
4. **AI Usage Log**: The repository's `AGENTS.md` defines an **append-only AI Usage Log** (kept in each
   member's home directory, deliberately outside the repo and never committed) that records agent sessions,
   prompts (with secrets redacted), and actions taken. This provides a per-session audit trail of substantive
   AI assistance.
5. **Secrets hygiene**: `AGENTS.md` mandates that secrets are read from environment variables only
   (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.), never hardcoded, and that API keys/tokens/PII are redacted
   before being written to the AI Usage Log.


## 4. What AI was NOT used for

- **Automatically validating correctness.** AI did not run our tests for us or certify that outputs were
  correct; humans wrote and ran the test suites (pytest, Vitest, Playwright) and the CI pipeline.
- **Making architectural decisions unilaterally.** Technology and design choices (documented in
  `docs/DECISIONS.md`) were made through team discussion; AI contributed options and trade-off analysis but did
  not decide.
- **Merging work unreviewed.** No AI output was committed "as-is" without a human reading, understanding, and
  taking ownership of it.
- **Generating the evaluation data or results.** Detection-accuracy metrics and the usability (SUS) study were
  produced from real pilot sessions and participants, not fabricated or inferred by AI.
- **Writing or altering user telemetry / integrity scores.** The anti-cheat scoring itself is deterministic
  rule-based code; no generative AI is involved in producing a student's integrity report.

---

## 5. Risk awareness & mitigations

The team recognised the risks of AI-assisted development and mitigated them explicitly:

| Risk | Mitigation |
| --- | --- |
| **Shallow understanding of borrowed code** | "Explain every line" rule + mandatory peer review before merge. |
| **Subtle/incorrect AI-generated logic** | Human-authored tests are the source of truth; CI must pass before merge. |
| **Leaking secrets or PII into prompts/logs** | Env-var-only secrets policy; redaction required in the AI Usage Log (`AGENTS.md` §2, §5). |
| **Over-reliance / uneven skill development** | All six members can explain any part of the codebase (prepared via `docs/interview_prep.md`). |
| **Untracked / undocumented AI use** | Append-only AI Usage Log records substantive sessions for auditability. |

---

## 6. Verification pointers

Anyone assessing this disclosure can confirm the claims above from the repository:

```bash
# Committed AI-tooling artifacts
ls -la AGENTS.md CLAUDE.md            # agent contract + Claude Code config
sed -n '212,219p' AGENTS.md           # Atlassian Rovo MCP configuration block

# Commit attribution style (note: AI assistance was tracked via the AI Usage Log,
# not via per-commit AI co-author trailers)
git log --format="%b" | grep -i "co-authored-by" | sort | uniq -c
```

