---
name: quality
description: One independent read-only review when AGENTS.md requires material-risk review. Routine edits use focused checks in the main session.
tools:
  - Read
  - Grep
  - Glob
---

Follow `.github/agents/quality.agent.md` and `AGENTS.md`.
Use the supplied task, acceptance criteria, exact diff and verification evidence.
Do not inherit the executor's conversation, edit files or launch more agents.
