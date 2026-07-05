---
name: python-environment
description: Bootstrap and use repo-local Python environments with uv and hardlinked package storage.
---

# Python Environment

Use the repository-local `.venv` and `uv` with hardlink mode. Never install project dependencies globally.

Default Windows bootstrap:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt
```
