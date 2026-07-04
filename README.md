# auto_learning_agent

Local MVP for a governed Codex/Cursor orchestrator repository.

This repository stores local policy, read-only audit tooling, knowledge schemas, retrieval policy, and publication previews. It does not write to `C:\Users\ppyxe\.codex` or `C:\Users\ppyxe\.cursor`; those folders are read-only audit targets unless a separate approved publication task exists.

## Layout

- `AGENTS.md` and `skills.md` define repo-local agent policy and repeatable workflows.
- `config/` stores the repository registry plus retrieval and promotion policies.
- `knowledge/` stores the index, catalog, schema, and local candidate directories.
- `scripts/` contains stdlib-only Python tools for audit, harvest, retrieval, promotion, preview publication, and TOML validation.
- `tests/` contains the MVP unit tests.
- `reports/` receives generated audit/readiness reports; generated report Markdown is ignored by git.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\validate_codex_config.py
.\.venv\Scripts\python.exe scripts\audit_global_instructions.py
git status --short --ignored
```
