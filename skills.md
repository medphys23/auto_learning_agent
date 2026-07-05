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
7. Run `scripts\audit_dependency_catalog.py` when checking whether dependency manifests are reflected in repo/global stack catalogs; treat missing packages as review flags, not automatic promotion.
8. Use `--profile optimized` only for shadow previews under `master/optimized/`; never pair it with global apply.
9. Global publication keeps only the newest 2 backup roots under `backups/global-sync/` by default; override with `--backup-keep N` only when the user explicitly asks.
10. Read colorized pipeline output: green `CLEAN`, yellow `DIRTY`, red `BLOCKED`.

**Verification:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\audit_context_budget.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\audit_dependency_catalog.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile optimized
git status --short --ignored
```

**Iteration notes:**
- 2026-07-04: Created the local MVP workflow with preview-only global publication and stdlib-only scripts.
- 2026-07-04: Added local GitHub repository discovery and deep-harvest workflow; dirty repositories are recorded but blocked from candidate extraction.
- 2026-07-05: Added top-level global instruction synthesis and guarded publication with backups, diffs, and explicit confirmation.
- 2026-07-05: Expanded safe repository knowledge harvesting with source maps, stack/dependency profiles, verification profiles, coverage reports, and a full README operator manual.
- 2026-07-05: Added the `run_orchestrator_pipeline.py` startup pipeline with tqdm phase logs and guarded global apply mode.
- 2026-07-05: Added colorama-backed clean/dirty/blocked repository status output to the pipeline log stream.
- 2026-07-05: User flagged excessive global-sync backups; publication now prunes older backup roots and retains the newest 2 by default.
- 2026-07-05: User noticed `colorama` was missing from published global stack catalog; synthesis now injects the orchestrator pipeline `tqdm`/`colorama` row into generated Codex and Cursor stack catalogs.
- 2026-07-05: Added dependency catalog audit report for `requirements.txt`, `pyproject.toml`, `package.json`, and common JS lockfiles; missing catalog mentions are review flags only.
- 2026-07-05: Added Shadow v1 token-optimization profile; legacy remains default, optimized writes preview artifacts under `master/optimized/` and refuses global apply.
