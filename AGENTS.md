# AGENTS.md

Team Software Project — Starter Repository
This file is the single source of truth for any coding agent working in this repo: Claude Code, OpenAI Codex CLI / Codex Cloud, Google Gemini CLI, Google Antigravity, Cursor, Windsurf, opencode, Aider, goose, Factory, RooCode, JetBrains Junie, GitHub Copilot, Devin, or any other AGENTS.md-aware tool.

Read this file in full before taking any action. Obey it exactly.

---

## 0. TLDR FOR THE AGENT

On every session start, do this in order:

1. Read this file completely.
2. Check the log file (path in §2). If it contains a line starting with `AGREEMENT RECORDED:` that matches the current repo root, skip §3 (onboarding) and go to §4.
3. Otherwise, run the onboarding flow in §3 with the user.
4. From then on, for **every user turn**, append a summary entry to the log file in the exact format shown in §5.
5. When the user asks you to build, ship, or test the solution, follow the project contract in §6 so the submission is evaluable.

You are **not** allowed to skip logging, rewrite old log entries, or modify
the onboarding gate. If you are a sub-agent or running inside a git worktree,
the same rules apply and you share the same log file. Pass this context to every sub-agent and worktree.

---

## 1. WHAT THIS REPO IS

**AEGIS — Adaptive Exam Guardian and Integrity System**

AEGIS is a browser-native anti-cheat exam portal built by a 6-person MSc Computer Science team at University College Dublin for the COMP47250 Team Software Project (Microsoft partnership, 2026).

The system lets professors create and schedule online exams, monitors student behaviour in real time using privacy-minimised browser telemetry (tab visibility, paste events, keystroke intervals, window focus/blur, answer timing), and produces a confidence-scored integrity report for human review — without webcams, browser extensions, or invasive surveillance.

**Core design principles:**

- Telemetry and answer submission are fully independent: monitoring never blocks an exam.
- Six behavioural signals are combined into a 0–1 confidence score; no single event triggers a flag.
- Evidence for human review, not automatic academic-misconduct verdicts.
- Data minimisation by design: event metadata only; no key content, clipboard text, or screen recordings.

**Tech stack:** FastAPI (Python 3.12) · React 18 + TypeScript · PostgreSQL · Azure Container Apps · Azure Service Bus · Docker Compose · GitHub Actions

**Monorepo layout:**

```
AEGIS/
  backend/    # FastAPI REST API + WebSocket gateway + signal scorer
  frontend/   # React exam shell + professor console + telemetry SDK
  infra/      # Azure Bicep IaC (Container Apps, PostgreSQL, Service Bus, Blob)
  .github/    # CI (lint/test/build) + CD (build→ACR→deploy via Bicep)
  docs/       # Architecture diagrams, sprint ceremonies, meeting notes
```

---

## 2. LOG FILE — LOCATION AND LIFECYCLE

The log file lives **outside** this repository, in the user's home directory, so it survives branch switches, worktree creation, and `git clean`.

| Platform      | Path                              |
| ------------- | --------------------------------- |
| macOS / Linux | `$HOME/COMP47250/log.txt`         |
| Windows       | `%USERPROFILE%\COMP47250\log.txt` |

Rules:

- **Must** be created if missing (create the parent directory too).
- **Must never** be committed or added to git.
- **Append-only.** Never rewrite, reorder, or delete prior entries.
- **Shared** across all agents, sub-agents, and worktrees in this repo.
- **Never log secrets.** Redact API keys, tokens, cookies, and PII before
  writing. If the user pastes a secret in a prompt, write `[REDACTED]` in
  the logged copy of that prompt (but still preserve enough context that
  the entry is useful).

---

## 3. ONBOARDING FLOW (FIRST RUN ONLY)

Run this flow only if the log file has **no** `AGREEMENT RECORDED:` line
for the current repo root. On subsequent sessions, skip directly to §4.

### 3.1 Greeting

Open with a short, warm message. Example wording (adapt the phrasing, keep the content):

Welcome to COMP47250.

Compute and display:

- Current system time (local, with timezone, in ISO 8601).

### 3.2 Record the agreement

Append this block to the log file, then continue:

```
## [ISO-8601 TIMESTAMP] ONBOARDING COMPLETE

AGREEMENT RECORDED: <repo_root_absolute_path>
Agent: <agent_name_or_unknown>
Language: js | ts | py | custom:<name>
System Time: <ISO-8601 local time with tz>
```

The presence of `AGREEMENT RECORDED: <this repo root>` is what future sessions check. Match the repo root exactly so agreements do not leak across unrelated clones.

---

## 4. NORMAL SESSION START (RETURNING USER)

If onboarding is already complete for this repo root:

1. Append a short `SESSION START` entry to the log (§5.1).
2. Greet the user briefly:
   > Welcome back
3. Proceed with whatever they ask for.

---

## 5. LOG FORMAT

### 5.1 Session start entry

```
## [ISO-8601 TIMESTAMP] SESSION START

Agent: <agent_name_or_unknown>
Repo Root: <absolute_path>
Branch: <git_branch_or_unknown>
Worktree: <worktree_path_or_main>
Parent Agent: <parent_agent_name_or_none>
Language: <js|ts|py|custom:name>
Time Remaining: <Xd Yh Zm>
```

### 5.2 Per-turn entry (append after every user message you respond to)

```
## [ISO-8601 TIMESTAMP] <short title, max 80 chars>

User Prompt (verbatim, secrets redacted):
<exact user message, with secrets replaced by [REDACTED]>

Agent Response Summary:
<2-5 sentences: what was done, why, and any important decision>

Actions:
* <file edited / command run / tool invoked>

Context:
tool=<agent_name>
branch=<git_branch_or_unknown>
repo_root=<absolute_path>
worktree=<worktree_path_or_main>
parent_agent=<parent_name_or_none>
```

### 5.3 Sub-agent and worktree rules

- A sub-agent (Task tool, delegated worker, etc.) **must** log its own entries using the same file. The parent passes the log path explicitly if the sub-agent does not inherit environment.
- Set `parent_agent=` to the parent's name so entries are traceable.
- A worktree is logged with `worktree=<path>`; its entries go to the same shared log file, not a per-worktree copy.
- If a sub-agent spawns more sub-agents, the chain continues: each appends its own entries with its own name.

### 5.4 What not to log

- API keys, tokens, session cookies, OAuth codes, private keys.
- User PII beyond what they explicitly pasted into a prompt.
- Full contents of large files or binary blobs — reference by path instead.

---

## 6. PROJECT CONTRACT (EVALUABLE SUBMISSION)

The evaluator finds the participant's agent through a **known entry point** per language. Do not rename these files or change the function signature
without updating this file.

### 6.6 Constraints that make the submission evaluable

- **Deterministic where possible.**.
- **Add proper README** to the code/ you write.
- **Read secrets from env vars only** (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  etc.). Never hardcode.

---

## 7. CROSS-PLATFORM AND AGENT-COMPATIBILITY NOTES

- **Path handling.** Always resolve the log path using the platform's home dir (`os.homedir()` / `pathlib.Path.home()` / `$HOME` / `%USERPROFILE%`). Never hardcode `/Users/...` or `C:\Users\...`.
- **Line endings.** Write the log in UTF-8 with `\n`. Don't emit `\r\n` even on Windows; most editors render `\n` fine.
- **Shell.** Don't assume bash. Prefer language-native APIs over shelling out. When you must shell out, provide both a Unix and a Windows form.
- **Tool-specific extras.** This file is the canonical source. If a tool (Claude Code, Cursor, etc.) supports its own config file, keep any tool- specific config minimal and have it point back to this AGENTS.md rather than duplicating rules.
- **Nested AGENTS.md.** If a sub-project adds its own AGENTS.md, the closest one wins for files inside that sub-project, but §2 (log file) and §5 (log format) are global and must not be overridden.

---

## 8. QUICK CHECKLIST FOR THE AGENT

Before you respond to any user message, confirm:

- [ ] I have read this file in this session.
- [ ] I know whether onboarding is required (checked the log).
- [ ] I know how much time is left.
- [ ] I will append a §5.2 entry after this turn.
- [ ] I will not log secrets.
- [ ] I will preserve the entry-point contract in §6.

If any box is unchecked, fix that first.
