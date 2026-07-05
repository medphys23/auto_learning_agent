# auto_learning_agent - Codex repeatable workflows

Inherits cross-repo patterns from `~/.codex/skills.md`. Dual canonical: mirror each workflow in `.cursor/skills/<name>/SKILL.md` when formal skill tooling is needed.

### Local MVP orchestrator bootstrap

**Triggered by:** Requests to implement or refresh the local orchestrator bootstrap.

**Preconditions:**
- Work from `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent`.
- Use the repo-local `.venv` interpreter.
- Install utility requirements with `uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt`.
- Treat global Codex/Cursor folders as read-only unless a separate approved publication task exists.

**Steps:**
1. Re-read `AGENTS.md`, `skills.md`, and the current git status.
2. Keep repo policy, config, schemas, scripts, tests, and reports local to this repository.
3. Run audit and validation scripts before reporting readiness.
4. Preserve generated reports as ignored local artifacts unless the user explicitly asks to track them.
5. For repository knowledge expansion, harvest only clean repos into candidate records and use coverage reports to explain blocked dirty repos.
6. For unattended local operation, run `scripts\run_orchestrator_pipeline.py --preview`; use `--apply-global --confirm-global-write` only for explicit global publication.
7. Read colorized pipeline output: green `CLEAN`, yellow `DIRTY`, red `BLOCKED`.

**Verification:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview
git status --short --ignored
```

**Iteration notes:**
- 2026-07-04: Created the local MVP workflow with preview-only global publication and stdlib-only scripts.
- 2026-07-04: Added local GitHub repository discovery and deep-harvest workflow; dirty repositories are recorded but blocked from candidate extraction.
- 2026-07-05: Added top-level global instruction synthesis and guarded publication with backups, diffs, and explicit confirmation.
- 2026-07-05: Expanded safe repository knowledge harvesting with source maps, stack/dependency profiles, verification profiles, coverage reports, and a full README operator manual.
- 2026-07-05: Added the `run_orchestrator_pipeline.py` startup pipeline with tqdm phase logs and guarded global apply mode.
- 2026-07-05: Added colorama-backed clean/dirty/blocked repository status output to the pipeline log stream.
