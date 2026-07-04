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
from harvest_repositories import harvest_repositories  # noqa: E402
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
from publish_global_rules import preview_publication  # noqa: E402


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

            first = harvest_repositories(registry, state, pending, base / "catalog.jsonl", base / "reports")
            second = harvest_repositories(registry, state, pending, base / "catalog.jsonl", base / "reports")

            self.assertEqual(first[0]["status"], "harvested")
            self.assertEqual(second[0]["status"], "skipped")
            self.assertEqual(len(list(pending.glob("*.json"))), 1)
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
            )

            self.assertEqual(results[0]["status"], "harvested")
            candidate_ids = {path.stem for path in pending.glob("*.json")}
            self.assertIn("clean-repo-repository-profile", candidate_ids)
            self.assertIn("clean-repo-verification-command-1", candidate_ids)
            self.assertIn("clean-repo-repository-constraints", candidate_ids)
            self.assertIn("clean-repo-workflow-demo-workflow", candidate_ids)
            catalog_ids = {json.loads(line)["id"] for line in catalog.read_text(encoding="utf-8").splitlines()}
            self.assertTrue(candidate_ids.issubset(catalog_ids))

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

    def test_publication_is_preview_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "reports"
            report = preview_publication(reports)
            self.assertTrue(report.exists())
            self.assertIn("Global writes performed: false", report.read_text(encoding="utf-8"))
            with self.assertRaises(RuntimeError):
                preview_publication(reports, apply=True)


if __name__ == "__main__":
    unittest.main()
