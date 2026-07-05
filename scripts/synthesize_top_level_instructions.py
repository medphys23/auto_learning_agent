from __future__ import annotations

import argparse
import difflib
import json
import shutil
from pathlib import Path
from typing import Any

from orchestrator_common import git_dirty_lines, load_repository_registry, read_toml, sha256_file, utc_now


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path.home() / ".codex"
CURSOR_HOME = Path.home() / ".cursor"

ORCHESTRATOR_BLOCK_ID = "global-knowledge-layer"
ORCHESTRATOR_BEGIN = f"<!-- BEGIN ORCHESTRATOR-MANAGED: {ORCHESTRATOR_BLOCK_ID} -->"
ORCHESTRATOR_END = f"<!-- END ORCHESTRATOR-MANAGED: {ORCHESTRATOR_BLOCK_ID} -->"

AGENT_FILES = {
    "workflow-router.toml": """name = "workflow_router"
description = "Classifies a task and retrieves the minimum relevant central and repository knowledge before implementation."
model_reasoning_effort = "low"
model_verbosity = "low"
sandbox_mode = "read-only"
developer_instructions = \"\"\"
Operate as a narrow routing and retrieval agent.
1. Read active global and repository instructions.
2. Classify the request by domain, stack, task type, risk, and deployment target.
3. Search the central index before opening full knowledge records.
4. Retrieve no more than 3 primary records, 2 supporting records, and 1 failure record by default.
5. Check runtime, framework, dependency, operating-system, deployment, interface, data, and security compatibility.
6. Retrieve repository-local workflows and decisions.
7. Return task classification, selected records, compatibility findings, recommended workflow, verification route, and records rejected as incompatible.
8. Do not modify files.
9. Do not spawn another agent.
10. Do not provide broad summaries unrelated to execution.
\"\"\"
""",
    "repository-harvester.toml": """name = "repository_harvester"
description = "Read-only inspector that extracts reusable, provenance-backed knowledge candidates from registered repositories."
model_reasoning_effort = "medium"
model_verbosity = "low"
sandbox_mode = "read-only"
developer_instructions = \"\"\"
Harvest only repositories present in the orchestrator repository registry.
Use incremental inspection: compare the stored commit or content fingerprint, skip unchanged repositories, and inspect changed commits and files first.
Read repository instructions, skills, architecture documentation, manifests, lockfiles, tests, CI/CD files, deployment files, releases, accepted implementation files, and failure notes.
Never execute repository scripts, modify a source repository, read or copy secrets, copy .env contents, ingest credentials, production payloads, PHI, personal data, large datasets, caches, dependencies, or build artifacts.
Never infer production success from a branch or filename alone.
Never promote a candidate directly.
For each candidate, provide type, summary, scope, applicability, incompatibility conditions, procedure, verification, rollback, exact source repository, commit/fingerprint, source paths, available test/deployment evidence, and confidence rationale.
Return no candidate when the lesson is routine, obvious from code, or not reusable.
Do not spawn another agent.
\"\"\"
""",
    "knowledge-synthesizer.toml": """name = "knowledge_synthesizer"
description = "Deduplicates knowledge candidates, resolves applicability boundaries, and proposes controlled promotion."
model_reasoning_effort = "high"
model_verbosity = "low"
sandbox_mode = "workspace-write"
developer_instructions = \"\"\"
Work only in the orchestrator repository knowledge, reports, and state paths.
For each candidate:
1. Find semantically overlapping records.
2. Compare scope, stack, versions, evidence, verification, reuse history, and risk.
3. Choose merge, specialize, supersede, reject, or retain-both.
4. Preserve provenance and links to all source records.
5. Keep repository-specific details local by default.
6. Require production evidence for production_proven.
7. Require explicit user approval for global architecture, security, authentication, network, database, deployment, cost, retention, regulated-domain, destructive, output-style, permission, sandbox, MCP, model, or provider changes.
8. Never publish to global Codex/Cursor folders.
9. Never erase deprecated knowledge.
10. Produce an exact promotion proposal and conflict report.
Do not spawn another agent.
\"\"\"
""",
    "verifier.toml": """name = "verifier"
description = "Independent read-focused reviewer for code changes, configuration, evidence, and knowledge promotion."
model_reasoning_effort = "high"
model_verbosity = "low"
sandbox_mode = "read-only"
developer_instructions = \"\"\"
Verify claims against repository state and executable evidence.
Check active instruction precedence, scope compliance, diff correctness, preservation of unrelated files, TOML syntax and schema validity, duplicate TOML keys, security and secret exclusions, targeted and broader test results, deployment evidence, rollback instructions, knowledge provenance, compatibility constraints, promotion eligibility, and Codex/Cursor semantic synchronization.
Do not accept claimed tests that were not run, production claims based only on branch names, global promotion without required approval, sandbox or approval weakening, hidden destructive behavior, or unresolved rule conflicts.
Return findings ordered by severity, followed by verified checks, skipped checks, residual risks, and a READY / CONDITIONALLY READY / NOT READY decision.
Do not modify files and do not spawn another agent.
\"\"\"
""",
}

AGENT_REGISTRATIONS = {
    "workflow_router": {
        "description": "Classifies tasks and retrieves the minimum compatible central and local knowledge.",
        "config_file": "agents/workflow-router.toml",
    },
    "repository_harvester": {
        "description": "Inspects registered repositories read-only and creates evidence-backed knowledge candidates.",
        "config_file": "agents/repository-harvester.toml",
    },
    "knowledge_synthesizer": {
        "description": "Deduplicates candidates and proposes scoped promotions or deprecations.",
        "config_file": "agents/knowledge-synthesizer.toml",
    },
    "verifier": {
        "description": "Validates implementation, evidence, configuration, and publication readiness.",
        "config_file": "agents/verifier.toml",
    },
}

ORCHESTRATOR_STACK_ROW = (
    "| **Orchestrator startup pipeline** | `tqdm`, `colorama` | auto_learning_agent | "
    "Progress bars and colorized clean/dirty/blocked repository status output; install only in the repo-local `.venv` |"
)

CURSOR_ORCHESTRATOR_STACK_ROW = (
    "| Orchestrator startup pipeline | tqdm, colorama | auto_learning_agent | "
    "Progress bars plus colorized clean/dirty/blocked repository status; repo-local `.venv` only |"
)

OPTIMIZED_AGENTS_MAX_BYTES = 8192

OPTIMIZED_GLOBAL_AGENTS = """# Global Codex instructions

## Core Rules
- Read the nearest applicable repository instructions before non-trivial edits.
- Make the smallest complete change that satisfies the task.
- Preserve public interfaces unless the task explicitly requires changing them.
- Do not commit, push, amend, force-push, reset, clean, delete user work, or run destructive Git commands without explicit approval.
- Never expose or hardcode secrets, credentials, tokens, PHI, private datasets, or production payloads.
- Use the repository's existing package manager, local environment, and lockfile.
- Ask before adding a new production dependency.
- Follow repository-defined verification and report exact commands, exit status, skipped checks, and residual risks.
- Global publication and high-risk configuration changes require explicit approval.
- Detailed workflows are loaded on demand from repository instructions, skills, or the orchestrator knowledge catalog.

## Orchestrator Knowledge
- Use `C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent` only for non-trivial cross-repo, migration, review, global-config, or repeatable-workflow tasks.
- Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
- Open the minimum relevant records and apply compatibility checks for repository, stack, OS, runtime, data sensitivity, and risk.
- Treat dirty repositories as advisory only; never promote uncommitted work as reusable knowledge.
- Repository-specific instructions override generalized reusable knowledge.
"""

OPTIMIZED_SKILLS: dict[str, str] = {
    "orchestrator-knowledge": """---
name: orchestrator-knowledge
description: Retrieve minimum governed knowledge from auto_learning_agent for non-trivial cross-repo or repeatable work.
---

# Orchestrator Knowledge

Use for cross-repo work, reviews, migrations, global instruction changes, or repeatable workflows.

1. Read active global and repository instructions.
2. Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl`.
3. Open only directly relevant records.
4. Check repository, stack, runtime, OS, data, and risk compatibility.
5. Verify through the target repository's `AGENTS.md`.
6. Record new reusable lessons as candidates, not global rules.
""",
    "python-environment": """---
name: python-environment
description: Bootstrap and use repo-local Python environments with uv and hardlinked package storage.
---

# Python Environment

Use the repository-local `.venv` and `uv` with hardlink mode. Never install project dependencies globally.

Default Windows bootstrap:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .\\.venv\\Scripts\\python.exe --link-mode hardlink -r requirements.txt
```
""",
    "office-com-deliverable": """---
name: office-com-deliverable
description: Create or repair review-grade Word and PowerPoint deliverables on Windows using Office COM.
---

# Office COM Deliverables

Prefer Word/PowerPoint COM for review-grade `.docx` and `.pptx` authoring on Windows. Use Python Office libraries only for parsing, tests, fallback, or explicit user opt-in. Always close documents and quit COM apps in `finally`.
""",
    "document-read-path": """---
name: document-read-path
description: Read Office/PDF/XLSX sources through a cached text conversion before loading binary content into context.
---

# Document Read Path

Convert trusted local documents into cached Markdown/text before analysis. Use repository-local dependencies and never commit conversion caches.
""",
    "lead-scraper": """---
name: lead-scraper
description: Build or maintain Playwright lead scrapers with resume checkpoints, tqdm progress, and contact-data safeguards.
---

# Lead Scraper

Use only on scraper repositories or scraper branches. Keep outputs under ignored `data/`, use resume-safe checkpoints, tqdm progress, polite delays, and never commit scraped contact exports.
""",
    "repository-scaffold": """---
name: repository-scaffold
description: Scaffold required repository instruction, verification, skill, Cursor mirror, and ignore files.
disable-model-invocation: true
---

# Repository Scaffold

Create root `AGENTS.md`, `skills.md`, `.cursor/rules/`, and `.gitignore` entries for new trusted repositories. Keep global behavior minimal and repository behavior local.
""",
    "stack-selection": """---
name: stack-selection
description: Select known repository stacks and dependency policies without loading the full global stack catalog.
---

# Stack Selection

Use repository manifests, `AGENTS.md`, and dependency audit reports first. Promote a package to global guidance only when it becomes a reusable cross-repo convention.
""",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def orchestrator_markdown_block() -> str:
    return f"""{ORCHESTRATOR_BEGIN}

## Orchestrator Knowledge Layer

Use `C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent` as the governed knowledge control plane for non-trivial work.

Activate this layer for multi-file changes, unclear bugs, cross-repo work, reviews, migrations, repeatable workflows, stack propagation, or global instruction changes. Skip it for tiny direct edits and simple factual questions unless the user explicitly asks for orchestrator behavior.

When active:

1. Read active global and repository instructions first.
2. Classify the task by repository, domain, stack, risk, and verification target.
3. Query the orchestrator `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
4. Retrieve only the relevant records: default maximum is 3 primary, 2 supporting, and 1 failure/anti-pattern.
5. Check compatibility before reuse: stack, runtime, OS, deployment, interface, data sensitivity, and repository rules.
6. Respect repository risk tags from `config/repositories.toml`, especially clinical/PHI, finance, scraper/contact-data, simulation-only robotics, auth/database, and global-config changes.
7. Treat dirty repositories as advisory only. Do not harvest or promote their current state as reusable knowledge until clean.
8. Keep repository-local knowledge local unless promotion criteria and evidence justify wider reuse.
9. Require explicit approval before global/canonical/security/auth/network/database/deployment/cost/model/provider/MCP/sandbox/approval-policy changes.
10. Verify using the target repository's `AGENTS.md -> ## Verification` section before reporting readiness.
11. Record reusable, non-obvious lessons as local candidates in the orchestrator repository after successful work.

This layer is a retrieval and governance system, not opaque memory and not a prompt dump. Existing explicit user instructions and safety constraints remain higher priority.

{ORCHESTRATOR_END}"""


def orchestrator_skill_section() -> str:
    return """### Orchestrator knowledge control plane

**Triggered by:** Non-trivial tasks, cross-repo work, reviews, migrations, repeatable workflows, global instruction changes, or explicit requests for the master/orchestrator agent.

**Preconditions:**

- Orchestrator repository: `C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent`.
- Use local clones under `C:\\Users\\ppyxe\\Documents\\GitHub` as the first source of truth unless a task explicitly needs remote GitHub metadata.
- Dirty repositories may be registered and reported, but their current working-tree state must not be promoted as reusable knowledge.

**Steps:**

1. Read active global and repository instructions.
2. Run or inspect `scripts\\discover_repositories.py` output when repository scope is unclear.
3. Query `knowledge\\catalog.jsonl` with the task's stack/risk/repository terms.
4. Open only the shortlisted full records under `knowledge\\pending`, `knowledge\\workflows`, or related knowledge folders.
5. Apply compatibility gates before reuse.
6. Verify through the target repository's `AGENTS.md -> ## Verification`.
7. Add new reusable lessons as candidates rather than canonical rules.

**Verification:**

```powershell
cd C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests
.\\.venv\\Scripts\\python.exe scripts\\validate_codex_config.py
.\\.venv\\Scripts\\python.exe scripts\\discover_repositories.py
.\\.venv\\Scripts\\python.exe scripts\\harvest_repositories.py
```

**Iteration notes:**

- 2026-07-05: Added global orchestrator workflow for governed retrieval, dirty-repo gating, and evidence-based promotion.
"""


def cursor_orchestrator_rule() -> str:
    return """---
description: Governed orchestrator knowledge retrieval for non-trivial cross-repo and repeatable work
alwaysApply: true
---

# Orchestrator knowledge layer

Use `C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent` as the governed knowledge control plane for non-trivial tasks.

Activate for multi-file changes, unclear bugs, reviews, migrations, stack propagation, repeatable workflows, cross-repo work, or global instruction changes. Skip for tiny direct edits unless the user asks for orchestrator behavior.

## Workflow

1. Read active global and repo instructions first.
2. Classify by repository, domain, stack, risk, and verification target.
3. Query `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
4. Retrieve only relevant records: 3 primary, 2 supporting, 1 failure/anti-pattern by default.
5. Check compatibility before reuse: stack, runtime, OS, deployment, interface, data sensitivity, and repo rules.
6. Respect risk tags in `config/repositories.toml`, especially clinical/PHI, finance, scraper/contact-data, simulation-only robotics, auth/database, and global-config work.
7. Treat dirty repositories as advisory only; do not promote current dirty state.
8. Verify with the target repository's `AGENTS.md -> ## Verification`.
9. Record reusable non-obvious lessons as candidates in the orchestrator repository.

Global/canonical/security/auth/network/database/deployment/cost/model/provider/MCP/sandbox/approval-policy changes require explicit approval.
"""


def cursor_orchestrator_skill() -> str:
    return """---
description: Retrieve and apply governed knowledge from the auto_learning_agent orchestrator repository for non-trivial work.
---

# Orchestrator knowledge control plane

Use when a task is non-trivial, cross-repo, review-heavy, migration-like, repeatable, or explicitly mentions the master/orchestrator agent.

## Steps

1. Read active global and repository instructions.
2. Inspect `C:\\Users\\ppyxe\\Documents\\GitHub\\auto_learning_agent\\knowledge\\catalog.jsonl` for concise matches.
3. Open only relevant full records.
4. Apply compatibility gates before reuse.
5. Verify with the target repo's `AGENTS.md`.
6. Keep new lessons as candidates unless evidence and approval justify promotion.

## Boundaries

- Do not harvest dirty repositories into reusable knowledge.
- Do not copy secrets, PHI, credentials, production payloads, or generated data.
- Do not publish global changes without backups, diffs, validation, and explicit approval.
"""


def replace_or_append_block(content: str, block: str) -> str:
    if ORCHESTRATOR_BEGIN in content and ORCHESTRATOR_END in content:
        start = content.index(ORCHESTRATOR_BEGIN)
        end = content.index(ORCHESTRATOR_END, start) + len(ORCHESTRATOR_END)
        return content[:start].rstrip() + "\n\n" + block + "\n\n" + content[end:].lstrip()
    return content.rstrip() + "\n\n" + block + "\n"


def insert_table_row_after(content: str, anchor: str, row: str) -> str:
    if row in content:
        return content
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if anchor in line:
            lines.insert(index + 1, row)
            return "\n".join(lines) + "\n"
    return content.rstrip() + "\n\n" + row + "\n"


def ensure_stack_catalog_entries(codex_agents: str) -> str:
    return insert_table_row_after(codex_agents, "| **Terminal progress (required)** |", ORCHESTRATOR_STACK_ROW)


def ensure_cursor_stack_catalog_entries(cursor_rule: str) -> str:
    return insert_table_row_after(cursor_rule, "| Terminal progress |", CURSOR_ORCHESTRATOR_STACK_ROW)


def replace_or_append_skill(content: str, section: str) -> str:
    heading = "### Orchestrator knowledge control plane"
    if heading in content:
        start = content.index(heading)
        next_heading = content.find("\n### ", start + 1)
        if next_heading == -1:
            return content[:start].rstrip() + "\n\n" + section.rstrip() + "\n"
        return content[:start].rstrip() + "\n\n" + section.rstrip() + "\n\n" + content[next_heading + 1 :].lstrip()
    return content.rstrip() + "\n\n---\n\n" + section.rstrip() + "\n"


def insert_key_in_table(config_text: str, table_name: str, key_line: str, key_name: str) -> str:
    data = read_toml_text(config_text)
    table = data.get(table_name, {})
    if isinstance(table, dict) and key_name in table:
        if table[key_name] is True:
            raise ValueError(f"[{table_name}].{key_name} is already true; refusing to weaken memory policy silently")
        return config_text
    table_header = f"[{table_name}]"
    lines = config_text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == table_header:
            insert_at = index + 1
            while insert_at < len(lines) and not lines[insert_at].lstrip().startswith("["):
                insert_at += 1
            lines.insert(insert_at, key_line)
            return "\n".join(lines) + "\n"
    return config_text.rstrip() + f"\n\n{table_header}\n{key_line}\n"


def read_toml_text(config_text: str) -> dict[str, Any]:
    import tomllib

    return tomllib.loads(config_text)


def merge_codex_config(config_text: str) -> tuple[str, list[str]]:
    report: list[str] = []
    original = config_text
    if not config_text.startswith("#:schema "):
        config_text = "#:schema https://developers.openai.com/codex/config-schema.json\n" + config_text
        report.append("Added Codex config schema header.")

    data = read_toml_text(config_text)
    features = data.get("features", {})
    if isinstance(features, dict) and features.get("memories") is True:
        raise ValueError("[features].memories is true; explicit user decision required before orchestrator publication")
    config_text = insert_key_in_table(config_text, "features", "memories = false", "memories")
    if config_text != original:
        report.append("Ensured [features].memories = false unless already false.")

    for key, value in (
        ("max_threads", "max_threads = 3"),
        ("max_depth", "max_depth = 1"),
        ("job_max_runtime_seconds", "job_max_runtime_seconds = 1800"),
    ):
        config_text = insert_key_in_table(config_text, "agents", value, key)

    data = read_toml_text(config_text)
    existing_agents = data.get("agents", {})
    if existing_agents and not isinstance(existing_agents, dict):
        raise ValueError("[agents] exists but is not a TOML table")
    if not isinstance(existing_agents, dict):
        existing_agents = {}

    for name, values in AGENT_REGISTRATIONS.items():
        existing = existing_agents.get(name)
        if existing:
            if not isinstance(existing, dict) or existing.get("config_file") != values["config_file"]:
                raise ValueError(f"Refusing to overwrite existing custom agent registration: {name}")
            continue
        config_text += (
            f"\n[agents.{name}]\n"
            f"description = \"{values['description']}\"\n"
            f"config_file = \"{values['config_file']}\"\n"
        )
    read_toml_text(config_text)
    report.append("Ensured bounded orchestrator custom agents under [agents].")
    return config_text, report


def validate_preservation(original: str, generated: str, required_tokens: list[str]) -> list[str]:
    missing = [token for token in required_tokens if token in original and token not in generated]
    return missing


def write_diff_report(report_path: Path, comparisons: list[tuple[str, str, str]]) -> None:
    lines = ["# Global Publication Diff", "", f"Generated: {utc_now()}", ""]
    for label, before, after in comparisons:
        lines.append(f"## {label}")
        diff = difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=f"current/{label}",
            tofile=f"master/{label}",
            lineterm="",
        )
        body = "\n".join(diff)
        lines.append("```diff")
        lines.append(body if body else "# No changes")
        lines.append("```")
        lines.append("")
    write_text(report_path, "\n".join(lines))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def optimized_config_fragment() -> str:
    lines = [
        "# Orchestrator-owned Codex config preview.",
        "# This fragment is not a full active config.toml copy.",
        "",
        "[agents]",
        "max_threads = 3",
        "max_depth = 1",
        "job_max_runtime_seconds = 1800",
        "",
    ]
    for name, values in AGENT_REGISTRATIONS.items():
        lines.extend(
            [
                f"[agents.{name}]",
                f"description = \"{values['description']}\"",
                f"config_file = \"{values['config_file']}\"",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_optimized_config_preview(reports_dir: Path, codex_config: str, fragment: str) -> None:
    diff = "\n".join(
        difflib.unified_diff(
            codex_config.splitlines(),
            fragment.splitlines(),
            fromfile="active/codex/config.toml",
            tofile="optimized/orchestrator-managed.toml",
            lineterm="",
        )
    )
    write_text(
        reports_dir / "optimized-config-merge-preview.md",
        "# Optimized Config Merge Preview\n\n"
        f"Generated: {utc_now()}\n\n"
        "The optimized path writes a narrow orchestrator-owned fragment only. It does not copy or apply the full active config.\n\n"
        "```diff\n"
        f"{diff if diff else '# No changes'}\n"
        "```\n",
    )
    write_json(
        reports_dir / "optimized-config-merge-preview.json",
        {
            "generated_at": utc_now(),
            "mode": "preview-only",
            "active_config_bytes": len(codex_config.encode("utf-8")),
            "optimized_fragment_bytes": len(fragment.encode("utf-8")),
            "owned_keys": ["agents.max_threads", "agents.max_depth", "agents.job_max_runtime_seconds", *[f"agents.{name}" for name in AGENT_REGISTRATIONS]],
            "applied": False,
        },
    )


def repository_instruction_paths(repo_path: Path) -> list[Path]:
    paths = [repo_path / "AGENTS.md", repo_path / "skills.md"]
    paths.extend(sorted(repo_path.glob("*/AGENTS.md")))
    return [path for path in paths if path.exists() and path.is_file()]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def write_repository_compatibility_reports(reports_dir: Path, optimized_agents: str) -> None:
    repositories = load_repository_registry(REPO_ROOT / "config" / "repositories.toml")
    rows: list[dict[str, Any]] = []
    for repo in repositories:
        repo_path = Path(str(repo.get("path", "")))
        instruction_paths = repository_instruction_paths(repo_path) if repo_path.exists() else []
        instruction_bytes = sum(path.stat().st_size for path in instruction_paths)
        instruction_text = "\n".join(read_text(path) for path in instruction_paths)
        dirty = git_dirty_lines(repo_path) if repo_path.exists() else []
        rows.append(
            {
                "id": repo.get("id"),
                "path": str(repo_path),
                "dirty_count": len(dirty),
                "instruction_files": [str(path) for path in instruction_paths],
                "repository_instruction_bytes": instruction_bytes,
                "optimized_chain_estimated_tokens": estimate_tokens(optimized_agents) + estimate_tokens(instruction_text),
                "mentions_global_skills": ".codex/skills.md" in instruction_text.lower() or "~/.codex/skills.md" in instruction_text.lower(),
                "mentions_global_stack_catalog": "global catalog" in instruction_text.lower() or "stack catalog" in instruction_text.lower(),
            }
        )
    write_json(reports_dir / "repository-compatibility-matrix.json", {"generated_at": utc_now(), "repositories": rows})
    lines = [
        "# Repository Compatibility Matrix",
        "",
        f"Generated: {utc_now()}",
        "",
        "Preview-only analysis. No registered source repositories were modified.",
        "",
        "| Repository | Dirty | Instruction files | Repo bytes | Optimized chain est. tokens | Global skill ref | Stack catalog ref |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['id']}` | {row['dirty_count']} | {len(row['instruction_files'])} | {row['repository_instruction_bytes']} | "
            f"{row['optimized_chain_estimated_tokens']} | {str(row['mentions_global_skills']).lower()} | {str(row['mentions_global_stack_catalog']).lower()} |"
        )
    write_text(reports_dir / "repository-compatibility-matrix.md", "\n".join(lines))


def write_optimized_cutover_plan(reports_dir: Path, optimized_agents_path: Path) -> None:
    result = {
        "generated_at": utc_now(),
        "applied": False,
        "cutover_allowed": False,
        "optimized_agents_path": str(optimized_agents_path),
        "required_future_command": ".\\.venv\\Scripts\\python.exe scripts\\plan_optimized_cutover.py",
        "requires_explicit_user_approval": True,
    }
    write_json(reports_dir / "optimized-cutover-plan.json", result)
    write_text(
        reports_dir / "optimized-cutover-plan.md",
        "# Optimized Cutover Plan\n\n"
        f"Generated: {result['generated_at']}\n\n"
        "- Status: preview only\n"
        "- No active global files were modified.\n"
        "- Legacy remains the default profile.\n"
        "- Future cutover must be a separate explicit task with backups, hash verification, canary checks, and rollback.\n",
    )


def synthesize_optimized(
    *,
    codex_home: Path,
    cursor_home: Path,
    master_root: Path,
    reports_dir: Path,
) -> dict[str, Any]:
    codex_config = read_text(codex_home / "config.toml")
    optimized_root = master_root / "optimized"
    optimized_codex = optimized_root / "codex"
    optimized_cursor = optimized_root / "cursor"
    optimized_skills = optimized_root / "agents" / "skills"

    agents = OPTIMIZED_GLOBAL_AGENTS
    agents_bytes = len(agents.encode("utf-8"))
    if agents_bytes > OPTIMIZED_AGENTS_MAX_BYTES:
        raise ValueError(f"optimized AGENTS.md exceeds {OPTIMIZED_AGENTS_MAX_BYTES} bytes: {agents_bytes}")
    write_text(optimized_codex / "AGENTS.md", agents)
    write_text(optimized_root / "shared" / "orchestrator-layer.md", orchestrator_markdown_block())
    fragment = optimized_config_fragment()
    write_text(optimized_codex / "config" / "orchestrator-managed.toml", fragment)
    for filename, content in AGENT_FILES.items():
        write_text(optimized_codex / "agents" / filename, content)
    for name, content in OPTIMIZED_SKILLS.items():
        write_text(optimized_skills / name / "SKILL.md", content)
    write_text(optimized_cursor / "rules" / "06-orchestrator-knowledge.mdc", cursor_orchestrator_rule())
    write_text(optimized_cursor / "skills" / "orchestrator-knowledge" / "SKILL.md", cursor_orchestrator_skill())

    write_optimized_config_preview(reports_dir, codex_config, fragment)
    write_repository_compatibility_reports(reports_dir, agents)
    write_optimized_cutover_plan(reports_dir, optimized_codex / "AGENTS.md")
    write_text(
        reports_dir / "top-level-synthesis.md",
        "# Top-Level Synthesis\n\n"
        f"Generated: {utc_now()}\n\n"
        "- Profile: optimized\n"
        "- Generated preview-only optimized Codex artifacts under `master/optimized/codex/`.\n"
        "- Generated preview-only optimized skills under `master/optimized/agents/skills/`.\n"
        "- No active global files were modified.\n",
    )
    return {
        "profile": "optimized",
        "master_root": str(optimized_root),
        "reports_dir": str(reports_dir),
        "codex_agents_bytes": agents_bytes,
        "codex_agents_sha256": sha256_file(optimized_codex / "AGENTS.md"),
        "config_fragment_sha256": sha256_file(optimized_codex / "config" / "orchestrator-managed.toml"),
    }


def synthesize(
    *,
    codex_home: Path = CODEX_HOME,
    cursor_home: Path = CURSOR_HOME,
    master_root: Path = REPO_ROOT / "master",
    reports_dir: Path = REPO_ROOT / "reports",
    profile: str = "legacy",
) -> dict[str, Any]:
    if profile == "optimized":
        return synthesize_optimized(
            codex_home=codex_home,
            cursor_home=cursor_home,
            master_root=master_root,
            reports_dir=reports_dir,
        )
    if profile != "legacy":
        raise ValueError(f"unsupported synthesis profile: {profile}")

    codex_agents = read_text(codex_home / "AGENTS.md")
    codex_skills = read_text(codex_home / "skills.md")
    codex_config = read_text(codex_home / "config.toml")

    generated_agents = ensure_stack_catalog_entries(replace_or_append_block(codex_agents, orchestrator_markdown_block()))
    generated_skills = replace_or_append_skill(codex_skills, orchestrator_skill_section())
    generated_config, config_report = merge_codex_config(codex_config)

    missing_agents = validate_preservation(
        codex_agents,
        generated_agents,
        ["Disk-efficient dependency isolation", "Python lead scraper pattern", "Windows Office automation", "Absolute prohibitions"],
    )
    missing_skills = validate_preservation(codex_skills, generated_skills, ["### tqdm progress bars", "### Practice operations dashboard"])
    if missing_agents or missing_skills:
        raise ValueError(f"Generated instructions lost required preserved content: {missing_agents + missing_skills}")

    master_codex = master_root / "codex"
    master_cursor = master_root / "cursor"
    write_text(master_root / "shared" / "orchestrator-layer.md", orchestrator_markdown_block())
    write_text(master_codex / "AGENTS.md", generated_agents)
    write_text(master_codex / "skills.md", generated_skills)
    write_text(master_codex / "config.toml", generated_config)
    for filename, content in AGENT_FILES.items():
        write_text(master_codex / "agents" / filename, content)

    cursor_rule_dir = cursor_home / "rules"
    (master_cursor / "rules").mkdir(parents=True, exist_ok=True)
    for path in sorted(cursor_rule_dir.glob("*.mdc")):
        if path.name == "03-stack-catalog.mdc":
            write_text(master_cursor / "rules" / path.name, ensure_cursor_stack_catalog_entries(read_text(path)))
        else:
            shutil.copy2(path, master_cursor / "rules" / path.name)
    write_text(master_cursor / "rules" / "06-orchestrator-knowledge.mdc", cursor_orchestrator_rule())
    write_text(master_cursor / "skills" / "orchestrator-knowledge" / "SKILL.md", cursor_orchestrator_skill())

    comparisons = [
        ("codex/AGENTS.md", codex_agents, generated_agents),
        ("codex/skills.md", codex_skills, generated_skills),
        ("codex/config.toml", codex_config, generated_config),
    ]
    write_diff_report(reports_dir / "global-publication-diff.md", comparisons)
    write_text(
        reports_dir / "config-merge-report.md",
        "# Config Merge Report\n\n"
        f"Generated: {utc_now()}\n\n"
        + "\n".join(f"- {item}" for item in config_report)
        + "\n",
    )
    write_text(
        reports_dir / "top-level-synthesis.md",
        "# Top-Level Synthesis\n\n"
        f"Generated: {utc_now()}\n\n"
        "- Generated Codex AGENTS, skills, config, and custom agent files under `master/codex/`.\n"
        "- Generated Cursor rule and skill files under `master/cursor/`.\n"
        "- Existing global instruction content was used as the base and preserved with additive orchestrator behavior.\n",
    )

    return {
        "profile": "legacy",
        "master_root": str(master_root),
        "reports_dir": str(reports_dir),
        "codex_agents_sha256": sha256_file(master_codex / "AGENTS.md"),
        "codex_skills_sha256": sha256_file(master_codex / "skills.md"),
        "codex_config_sha256": sha256_file(master_codex / "config.toml"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthesize top-level Codex/Cursor orchestrator instructions.")
    parser.add_argument("--preview", action="store_true", help="Generate master files and reports.")
    parser.add_argument("--codex-home", type=Path, default=CODEX_HOME)
    parser.add_argument("--cursor-home", type=Path, default=CURSOR_HOME)
    parser.add_argument("--master-root", type=Path, default=REPO_ROOT / "master")
    parser.add_argument("--reports-dir", type=Path, default=REPO_ROOT / "reports")
    parser.add_argument("--profile", choices=("legacy", "optimized"), default="legacy")
    args = parser.parse_args()
    result = synthesize(
        codex_home=args.codex_home,
        cursor_home=args.cursor_home,
        master_root=args.master_root,
        reports_dir=args.reports_dir,
        profile=args.profile,
    )
    print(f"Synthesized top-level instructions under {result['master_root']}")
    print(f"Reports written to {result['reports_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
