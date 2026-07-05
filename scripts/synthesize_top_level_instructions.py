from __future__ import annotations

import argparse
import difflib
import shutil
from pathlib import Path
from typing import Any

from orchestrator_common import read_toml, sha256_file, utc_now


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


def synthesize(
    *,
    codex_home: Path = CODEX_HOME,
    cursor_home: Path = CURSOR_HOME,
    master_root: Path = REPO_ROOT / "master",
    reports_dir: Path = REPO_ROOT / "reports",
) -> dict[str, Any]:
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
    args = parser.parse_args()
    result = synthesize(
        codex_home=args.codex_home,
        cursor_home=args.cursor_home,
        master_root=args.master_root,
        reports_dir=args.reports_dir,
    )
    print(f"Synthesized top-level instructions under {result['master_root']}")
    print(f"Reports written to {result['reports_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
