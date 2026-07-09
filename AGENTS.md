# auto_learning_agent - agent instructions

Inherits global rules from `~/.codex/AGENTS.md` and `~/.cursor/rules/`.

**Cursor mirror:** [`.cursor/rules/`](.cursor/rules/) - keep in sync with this file.

## Purpose
This repository is the local MVP for a governed Codex/Cursor orchestrator. It stores repository-local policy, read-only audit tooling, knowledge schemas, retrieval policy, and publication previews. It must not directly mutate user-level Codex or Cursor folders.

## Stack
- Python 3.11 standard library scripts.
- TOML parsing uses `tomllib`.
- Tests use `unittest`.
- Startup pipeline progress uses `tqdm` and `colorama` from the repo-local `.venv`.
- Existing PDF source material remains tracked as reference input.

## Dependency isolation
- Install Python packages only into the repo-root `.venv` unless an incompatible subproject has a documented local `.venv`.
- Bootstrap on Windows with `uv venv --python 3.11 .venv`.
- Install repo utility requirements with `uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt`.
- Use the shared `uv` cache on the same filesystem as the repo. Never use bare/global `pip`, `pip install --user`, `uv pip --system`, `--link-mode copy`, or `--no-cache`.
- Keep `.venv/`, `venv/`, and generated dependency directories in `.gitignore` and out of git.

## Uses from global catalog
- Python 3.11 with repo-local `.venv`.
- MarkItDown/PDF reading policy applies when analyzing future Office/PDF inputs.
- No new production dependency is required for the MVP scripts.

## Verification
Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
.\.venv\Scripts\python.exe scripts\audit_context_budget.py
.\.venv\Scripts\python.exe scripts\discover_repositories.py
.\.venv\Scripts\python.exe scripts\harvest_repositories.py
.\.venv\Scripts\python.exe scripts\audit_dependency_catalog.py
.\.venv\Scripts\python.exe scripts\retrieve_knowledge.py --query orsi --status candidate
.\.venv\Scripts\python.exe scripts\retrieve_knowledge_for_repo.py --cwd .
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\synthesize_top_level_instructions.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\publish_global_rules.py --preview --profile optimized
.\.venv\Scripts\python.exe scripts\propagate_orchestrator_retrieval_hints.py
.\.venv\Scripts\python.exe scripts\run_optimized_knowledge_cycle.py --strict
.\.venv\Scripts\python.exe scripts\run_optimized_cutover.py --allow-dirty
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile legacy
.\.venv\Scripts\python.exe scripts\run_orchestrator_pipeline.py --preview --profile optimized
git status --short --ignored
```

## Repo skills catalog
Maintain [`skills.md`](skills.md) beside this file. Document repeatable Codex workflows per `~/.codex/AGENTS.md`. Inherit cross-repo patterns from `~/.codex/skills.md`. Cursor mirror: `.cursor/skills/<name>/SKILL.md` when workflows exist.

## Repo-specific rules
- Global folders `C:\Users\ppyxe\.codex` and `C:\Users\ppyxe\.cursor` are read-only audit targets unless the user explicitly approves a separate publication step.
- `scripts/publish_global_rules.py` is preview-first and must refuse unconfirmed global writes.
- `scripts/publish_global_rules.py --apply --confirm-global-write` may write global Codex/Cursor files only after the user explicitly requests global publication.
- `scripts/run_orchestrator_pipeline.py --apply-global --confirm-global-write` runs the local pipeline and then performs the same guarded global publication.
- Global publication must create repo-local backups under `backups/global-sync/<timestamp>/` before writing.
- Generated reports in `reports/*.md` are local outputs and are ignored by git.
- Repository discovery and harvesting must remain read-only against registered source repositories.
- Dirty registered repositories must be recorded in state/reports but skipped for candidate extraction.
- Exception: this orchestrator repository has `allow_dirty_harvest = true` because running the orchestrator normally regenerates local state, reports, knowledge candidates, and master previews. This exception is local to `auto_learning_agent`; do not reuse it for source repos without explicit approval.
- Never harvest secrets, `.env` content, SQLite state, sessions, logs, plugin caches, dependency directories, build artifacts, or generated caches.
- Harvested knowledge must be concise, provenance-backed candidate metadata; do not mirror raw repositories into this repo.
- Knowledge promotion starts as local candidates. Global, canonical, security, sandbox, approval, model/provider, MCP, authentication, network, database, deployment, cost, retention, regulated-domain, destructive-command, or output-style changes require explicit approval metadata.

## Stack propagation
When introducing a new library, skill, or tool here, update `~/.codex/AGENTS.md` and propagate to other repos per global policy.

## Git
- Do not commit unless the user asks.
- Single checkout only - never use `git worktree add`.

<!-- BEGIN ORCHESTRATOR-MANAGED: knowledge-retrieval -->

## Orchestrator Knowledge (Optimized)
- Index-first: `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent\knowledge\INDEX.md` then `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent\knowledge\catalog.jsonl`.
- Repo-scoped retrieval: `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent\scripts\retrieve_knowledge_for_repo.py --cwd C:\Users\ppyxe\Documents\GitHub\auto_learning_agent`.
- Open only shortlisted full records; repo `AGENTS.md` overrides catalog guidance.

<!-- END ORCHESTRATOR-MANAGED: knowledge-retrieval -->

