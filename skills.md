# auto_learning_agent - Codex repeatable workflows

Inherits cross-repo patterns from `~/.codex/skills.md`. Dual canonical: mirror each workflow in `.cursor/skills/<name>/SKILL.md` when formal skill tooling is needed.

### Local MVP orchestrator bootstrap

**Triggered by:** Requests to implement or refresh the local orchestrator bootstrap.

**Preconditions:**
- Work from `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent`.
- Use the repo-local `.venv` interpreter.
- Treat global Codex/Cursor folders as read-only unless a separate approved publication task exists.

**Steps:**
1. Re-read `AGENTS.md`, `skills.md`, and the current git status.
2. Keep repo policy, config, schemas, scripts, tests, and reports local to this repository.
3. Run audit and validation scripts before reporting readiness.
4. Preserve generated reports as ignored local artifacts unless the user explicitly asks to track them.

**Verification:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
git status --short --ignored
```

**Iteration notes:**
- 2026-07-04: Created the local MVP workflow with preview-only global publication and stdlib-only scripts.
- 2026-07-04: Added local GitHub repository discovery and deep-harvest workflow; dirty repositories are recorded but blocked from candidate extraction.
