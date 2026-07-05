from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from discover_repositories import discover_repositories, write_registry  # noqa: E402
from harvest_repositories import harvest_repositories, manifest_signals, source_map_summary  # noqa: E402
from orchestrator_common import (  # noqa: E402
    extract_code_block_commands,
    extract_markdown_section,
    extract_skill_sections,
    retrieve_records,
    sample_candidate_record,
    should_audit_file,
    should_harvest_text_file,
    validate_knowledge_record,
)
from publish_global_rules import publish_global_rules  # noqa: E402
from synthesize_top_level_instructions import merge_codex_config, synthesize  # noqa: E402


class OrchestratorMvpTests(unittest.TestCase):
    def init_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)

    def test_repo_toml_files_parse(self) -> None:
        files = [
            ROOT / ".codex" / "config.toml",
            *sorted((ROOT / ".codex" / "agents").glob("*.toml")),
            *sorted((ROOT / "config").glob("*.toml")),
        ]
        self.assertGreaterEqual(len(files), 8)
        for path in files:
            with self.subTest(path=path):
                tomllib.loads(path.read_text(encoding="utf-8"))

    def test_knowledge_record_validation_accepts_valid_and_rejects_missing_required(self) -> None:
        record = sample_candidate_record("valid-record")
        self.assertEqual(validate_knowledge_record(record), [])

        for missing in ("status", "provenance", "verification"):
            invalid = dict(record)
            invalid.pop(missing)
            errors = validate_knowledge_record(invalid)
            self.assertTrue(any(missing in error for error in errors), errors)

    def test_audit_excludes_sensitive_and_runtime_paths(self) -> None:
        self.assertFalse(should_audit_file(Path(r"C:\Users\ppyxe\.codex\auth.json")))
        self.assertFalse(should_audit_file(Path(r"C:\Users\ppyxe\.codex\cache\tool.md")))
        self.assertFalse(should_audit_file(Path(r"C:\Users\ppyxe\.codex\logs_2.sqlite")))
        self.assertTrue(should_audit_file(Path(r"C:\Users\ppyxe\.codex\AGENTS.md")))
        self.assertTrue(should_audit_file(Path(r"C:\Users\ppyxe\.cursor\rules\00-orchestration.mdc")))

    def test_discovery_finds_local_git_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "demo_repo"
            repo.mkdir()
            self.init_git_repo(repo)
            (repo / "AGENTS.md").write_text("# demo\n", encoding="utf-8")
            (repo / "skills.md").write_text("# skills\n", encoding="utf-8")

            discovered = discover_repositories(root)

            self.assertEqual(len(discovered), 1)
            self.assertEqual(discovered[0]["id"], "demo-repo")
            self.assertTrue(discovered[0]["has_agents"])
            self.assertTrue(discovered[0]["has_skills"])

    def test_registry_write_preserves_existing_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "repositories.toml"
            registry.write_text(
                "[[repositories]]\n"
                "id = 'demo-repo'\n"
                "name = 'old'\n"
                "path = 'old'\n"
                "enabled = true\n"
                "scope = 'old'\n"
                "risk_tags = []\n"
                "stack_tags = []\n"
                "harvest_mode = 'deep_when_clean'\n"
                "notes = 'keep this note'\n",
                encoding="utf-8",
            )
            write_registry(
                registry,
                [
                    {
                        "id": "demo-repo",
                        "name": "demo_repo",
                        "path": r"C:\demo_repo",
                        "remote": "https://example.invalid/demo.git",
                        "current_branch": "main",
                        "enabled": True,
                        "scope": "sandbox",
                        "risk_tags": ["sandbox"],
                        "stack_tags": ["python"],
                        "harvest_mode": "deep_when_clean",
                    }
                ],
            )
            data = tomllib.loads(registry.read_text(encoding="utf-8"))
            self.assertEqual(data["repositories"][0]["notes"], "keep this note")
            self.assertEqual(data["repositories"][0]["name"], "demo_repo")

    def test_harvest_skips_unchanged_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# demo\n", encoding="utf-8")
            state = base / "state" / "repository-snapshots.json"
            pending = base / "pending"
            registry = [{"id": "demo_repo", "path": str(repo), "enabled": True}]

            first = harvest_repositories(
                registry,
                state,
                pending,
                base / "catalog.jsonl",
                base / "reports",
                base / "knowledge" / "INDEX.md",
            )
            second = harvest_repositories(
                registry,
                state,
                pending,
                base / "catalog.jsonl",
                base / "reports",
                base / "knowledge" / "INDEX.md",
            )

            self.assertEqual(first[0]["status"], "harvested")
            self.assertEqual(second[0]["status"], "skipped")
            self.assertGreaterEqual(len(list(pending.glob("*.json"))), 4)
            self.assertIn("demo_repo", json.loads(state.read_text(encoding="utf-8"))["repositories"])

    def test_dirty_repo_is_registered_but_not_harvested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "dirty"
            repo.mkdir()
            self.init_git_repo(repo)
            (repo / "README.md").write_text("# dirty\n", encoding="utf-8")
            state = base / "state.json"
            pending = base / "pending"

            results = harvest_repositories(
                [{"id": "dirty_repo", "path": str(repo), "enabled": True}],
                state,
                pending,
                base / "catalog.jsonl",
                base / "reports",
                base / "knowledge" / "INDEX.md",
            )

            self.assertEqual(results[0]["status"], "blocked_dirty_worktree")
            self.assertEqual(list(pending.glob("*.json")), [])
            snapshot = json.loads(state.read_text(encoding="utf-8"))["repositories"]["dirty_repo"]
            self.assertEqual(snapshot["harvest_status"], "blocked_dirty_worktree")

    def test_clean_repo_generates_candidates_and_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "clean"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(
                "# clean\n\n"
                "## Purpose\nDemo purpose.\n\n"
                "## Stack\n- Python\n\n"
                "## Verification\n```powershell\npython -m unittest\n```\n\n"
                "## Repo-specific rules\n- Never commit secrets.\n",
                encoding="utf-8",
            )
            (repo / "skills.md").write_text(
                "# skills\n\n"
                "### Demo workflow\n\n"
                "**Steps:**\n"
                "1. Inspect files.\n"
                "2. Run tests.\n",
                encoding="utf-8",
            )
            state = base / "state.json"
            pending = base / "pending"
            catalog = base / "catalog.jsonl"

            results = harvest_repositories(
                [{"id": "clean_repo", "name": "clean", "path": str(repo), "stack_tags": ["python"], "risk_tags": []}],
                state,
                pending,
                catalog,
                base / "reports",
                base / "knowledge" / "INDEX.md",
            )

            self.assertEqual(results[0]["status"], "harvested")
            candidate_ids = {path.stem for path in pending.glob("*.json")}
            self.assertIn("clean-repo-repository-profile", candidate_ids)
            self.assertIn("clean-repo-source-map", candidate_ids)
            self.assertIn("clean-repo-stack-dependency-profile", candidate_ids)
            self.assertIn("clean-repo-verification-profile", candidate_ids)
            self.assertIn("clean-repo-verification-command-1", candidate_ids)
            self.assertIn("clean-repo-repository-constraints", candidate_ids)
            self.assertIn("clean-repo-workflow-demo-workflow", candidate_ids)
            catalog_entries = [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines()]
            catalog_ids = {entry["id"] for entry in catalog_entries}
            self.assertTrue(candidate_ids.issubset(catalog_ids))
            self.assertTrue(all(Path(entry["record_path"]).exists() for entry in catalog_entries))
            self.assertIn("clean_repo", (base / "reports" / "knowledge-coverage.md").read_text(encoding="utf-8"))
            self.assertIn("Source map", (base / "reports" / "repository-knowledge-matrix.md").read_text(encoding="utf-8"))
            self.assertIn("clean_repo", (base / "knowledge" / "INDEX.md").read_text(encoding="utf-8"))

    def test_manifest_package_scripts_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"test": "vitest", "build": "next build"},
                        "dependencies": {"next": "16.0.0", "react": "19.0.0"},
                        "devDependencies": {"vitest": "latest"},
                    }
                ),
                encoding="utf-8",
            )

            signals = manifest_signals(repo)

            self.assertEqual(signals[0]["path"], "package.json")
            self.assertEqual(signals[0]["scripts"], ["build", "test"])
            self.assertIn("next", signals[0]["dependencies"])

    def test_source_map_excludes_sensitive_generated_and_data_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            (repo / "data").mkdir()
            (repo / "data" / "leads.json").write_text("[]\n", encoding="utf-8")
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "pkg.js").write_text("bad\n", encoding="utf-8")
            (repo / ".env").write_text("TOKEN=value\n", encoding="utf-8")

            summary = source_map_summary(repo)
            examples = [example for area in summary["areas"] for example in area["examples"]]

            self.assertIn("src/app.py", examples)
            self.assertNotIn("data/leads.json", examples)
            self.assertNotIn("node_modules/pkg.js", examples)
            self.assertNotIn(".env", examples)

    def test_harvest_excludes_sensitive_generated_and_data_paths(self) -> None:
        self.assertFalse(should_harvest_text_file(Path(r"C:\repo\.env")))
        self.assertFalse(should_harvest_text_file(Path(r"C:\repo\data\leads.json")))
        self.assertFalse(should_harvest_text_file(Path(r"C:\repo\scraper_outputs\latest.json")))
        self.assertFalse(should_harvest_text_file(Path(r"C:\repo\state.sqlite")))
        self.assertFalse(should_harvest_text_file(Path(r"C:\repo\node_modules\pkg\index.js")))

    def test_extracts_verification_commands_and_skill_headings(self) -> None:
        agents = "## Verification\n```powershell\npython -m unittest\n# comment\npython -m compileall src\n```\n## Git\n"
        verification = extract_markdown_section(agents, "verification")
        self.assertEqual(extract_code_block_commands(verification), ["python -m unittest", "python -m compileall src"])

        skills = "### First workflow\n1. A\n\n### Second workflow\n- B\n"
        self.assertEqual([section["title"] for section in extract_skill_sections(skills)], ["First workflow", "Second workflow"])

    def test_retrieval_respects_configured_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            catalog = base / "catalog.jsonl"
            policy = base / "retrieval-policy.toml"
            policy.write_text(
                "[budgets]\nprimary_records = 2\nsupporting_records = 1\nfailure_records = 1\n",
                encoding="utf-8",
            )
            records = []
            for index in range(10):
                record = sample_candidate_record(f"record-{index}")
                record["tags"] = ["budget-test"]
                record["confidence"]["score"] = index / 10
                records.append(json.dumps(record))
            catalog.write_text("\n".join(records) + "\n", encoding="utf-8")

            retrieved = retrieve_records(catalog, policy, tags=["budget-test"])

            self.assertEqual(len(retrieved), 4)

    def test_readme_contains_operator_manual_sections(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for heading in (
            "## Current Phase",
            "## Master Publication Model",
            "## Knowledge Lifecycle",
            "## Safety Boundaries",
            "## How To Know Whether A Repo Is Known",
            "## Troubleshooting And Rollback",
        ):
            self.assertIn(heading, readme)

    def write_minimal_global_home(self, base: Path) -> tuple[Path, Path]:
        codex = base / ".codex"
        cursor = base / ".cursor"
        (codex / "agents").mkdir(parents=True)
        (cursor / "rules").mkdir(parents=True)
        (cursor / "skills").mkdir(parents=True)
        (codex / "AGENTS.md").write_text(
            "# Global Codex agent instructions\n\n## Working agreements\n- Preserve this rule.\n",
            encoding="utf-8",
        )
        (codex / "skills.md").write_text(
            "# Global Codex repeatable workflows\n\n### tqdm progress bars\n\n**Steps:**\n1. Keep this.\n",
            encoding="utf-8",
        )
        (codex / "config.toml").write_text(
            'model = "gpt-5.5"\n\n[plugins."github@openai-curated"]\nenabled = true\n\n[features]\njs_repl = false\n',
            encoding="utf-8",
        )
        (cursor / "rules" / "00-orchestration.mdc").write_text(
            "---\ndescription: Test rule\nalwaysApply: true\n---\n\n# Test rule\n",
            encoding="utf-8",
        )
        return codex, cursor

    def test_synthesis_preserves_existing_content_and_adds_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            result = synthesize(
                codex_home=codex,
                cursor_home=cursor,
                master_root=base / "master",
                reports_dir=base / "reports",
            )

            agents = (base / "master" / "codex" / "AGENTS.md").read_text(encoding="utf-8")
            skills = (base / "master" / "codex" / "skills.md").read_text(encoding="utf-8")
            config = tomllib.loads((base / "master" / "codex" / "config.toml").read_text(encoding="utf-8"))

            self.assertIn("Preserve this rule", agents)
            self.assertIn("Orchestrator Knowledge Layer", agents)
            self.assertIn("### tqdm progress bars", skills)
            self.assertIn("### Orchestrator knowledge control plane", skills)
            self.assertEqual(config["features"]["memories"], False)
            self.assertIn("workflow_router", config["agents"])
            self.assertTrue((base / "master" / "cursor" / "rules" / "06-orchestrator-knowledge.mdc").exists())
            self.assertIn("codex_agents_sha256", result)

    def test_config_merge_preserves_plugins_and_refuses_memory_true(self) -> None:
        config = 'model = "gpt-5.5"\n\n[plugins."github@openai-curated"]\nenabled = true\n'
        merged, report = merge_codex_config(config)
        data = tomllib.loads(merged)
        self.assertEqual(data["plugins"]["github@openai-curated"]["enabled"], True)
        self.assertEqual(data["features"]["memories"], False)
        self.assertIn("workflow_router", data["agents"])
        self.assertTrue(report)

        merged_again, _ = merge_codex_config(merged)
        merged_again_data = tomllib.loads(merged_again)
        self.assertEqual(
            merged_again_data["agents"]["workflow_router"]["config_file"],
            "agents/workflow-router.toml",
        )

        with self.assertRaises(ValueError):
            merge_codex_config("[features]\nmemories = true\n")

        with self.assertRaises(ValueError):
            merge_codex_config("[agents.workflow_router]\nconfig_file = \"agents/other.toml\"\n")

    def test_publish_requires_confirmation_and_applies_with_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            preview = publish_global_rules(
                reports_dir=base / "reports",
                master_root=base / "master",
                backup_base=base / "backups",
                codex_home=codex,
                cursor_home=cursor,
            )
            self.assertEqual(preview["mode"], "preview")
            self.assertIn("Global writes performed: false", (base / "reports" / "publication-preview.md").read_text(encoding="utf-8"))

            with self.assertRaises(RuntimeError):
                publish_global_rules(
                    reports_dir=base / "reports",
                    master_root=base / "master",
                    backup_base=base / "backups",
                    codex_home=codex,
                    cursor_home=cursor,
                    apply=True,
                )

            applied = publish_global_rules(
                reports_dir=base / "reports",
                master_root=base / "master",
                backup_base=base / "backups",
                codex_home=codex,
                cursor_home=cursor,
                apply=True,
                confirm_global_write=True,
            )
            self.assertEqual(applied["mode"], "applied")
            self.assertTrue((Path(applied["backup_root"]) / "codex" / "AGENTS.md").exists())
            self.assertIn("Orchestrator Knowledge Layer", (codex / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertTrue((cursor / "skills" / "orchestrator-knowledge" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
