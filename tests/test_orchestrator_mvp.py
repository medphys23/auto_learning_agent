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

from audit_context_budget import audit_context_budget  # noqa: E402
from audit_dependency_catalog import audit_dependency_catalog, parse_requirement_line  # noqa: E402
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
from propagate_orchestrator_retrieval_hints import propagate_hints  # noqa: E402
from propagate_graphify_integration import policy_block, propagate_graphify, replace_or_append  # noqa: E402
from query_graph import build_query_command, resolve_graph  # noqa: E402
from retrieve_knowledge_for_repo import retrieve_for_repo  # noqa: E402
from run_optimized_cutover import build_cycle_command  # noqa: E402
from run_optimized_knowledge_cycle import build_steps as build_optimized_cycle_steps  # noqa: E402
from run_orchestrator_pipeline import build_steps, parse_discovery_lines, parse_harvest_lines  # noqa: E402
from run_graphify_cycle import (  # noqa: E402
    merge_graphs,
    parse_version,
    preflight_repository,
    scan_graph,
    structural_graph_sha256,
    write_empty_repository_graph,
)
from synthesize_top_level_instructions import merge_codex_config, synthesize  # noqa: E402
from validate_codex_routing import validate_routing_event  # noqa: E402


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

    def test_dirty_repo_can_be_harvested_with_explicit_registry_exception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "dirty_allowed"
            repo.mkdir()
            self.init_git_repo(repo)
            (repo / "AGENTS.md").write_text(
                "# dirty allowed\n\n"
                "## Purpose\nDemo.\n\n"
                "## Verification\n```powershell\npython -m unittest\n```\n",
                encoding="utf-8",
            )
            state = base / "state.json"
            pending = base / "pending"

            results = harvest_repositories(
                [
                    {
                        "id": "dirty_allowed",
                        "name": "dirty_allowed",
                        "path": str(repo),
                        "enabled": True,
                        "allow_dirty_harvest": True,
                    }
                ],
                state,
                pending,
                base / "catalog.jsonl",
                base / "reports",
                base / "knowledge" / "INDEX.md",
            )

            self.assertEqual(results[0]["status"], "harvested")
            self.assertEqual(results[0]["reason"], "dirty worktree allowed by registry")
            self.assertGreater(results[0]["dirty_count"], 0)
            self.assertGreater(len(list(pending.glob("dirty-allowed-*.json"))), 0)
            snapshot = json.loads(state.read_text(encoding="utf-8"))["repositories"]["dirty_allowed"]
            self.assertEqual(snapshot["harvest_status"], "harvested")
            self.assertGreater(snapshot["dirty_count"], 0)

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

    def test_dependency_catalog_audit_flags_missing_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# repo\n\n## Stack\n- Python\n- requests\n", encoding="utf-8")
            (repo / "requirements.txt").write_text("requests==2.32.0\ncolorama==0.4.6\n", encoding="utf-8")
            (repo / "package.json").write_text(
                json.dumps({"dependencies": {"react": "19.0.0"}, "devDependencies": {"vitest": "latest"}}),
                encoding="utf-8",
            )
            codex = base / ".codex"
            cursor = base / ".cursor"
            (codex).mkdir()
            (cursor / "rules").mkdir(parents=True)
            (codex / "AGENTS.md").write_text("requests\nreact\n", encoding="utf-8")
            (codex / "skills.md").write_text("", encoding="utf-8")
            (cursor / "rules" / "03-stack-catalog.mdc").write_text("react\n", encoding="utf-8")
            registry = base / "repositories.toml"
            registry.write_text(
                "[[repositories]]\n"
                "id = 'repo'\n"
                "name = 'repo'\n"
                f"path = '{repo.as_posix()}'\n"
                "enabled = true\n",
                encoding="utf-8",
            )

            result = audit_dependency_catalog(
                registry_path=registry,
                reports_dir=base / "reports",
                codex_home=codex,
                cursor_home=cursor,
            )

            audited = result["repositories"][0]
            self.assertEqual(audited["package_count"], 4)
            self.assertIn("colorama", audited["missing_from_global_catalog"])
            self.assertIn("vitest", audited["missing_from_repo_catalog"])
            self.assertTrue((base / "reports" / "dependency-catalog-audit.md").exists())

    def test_requirement_line_parser_skips_options_and_extracts_names(self) -> None:
        self.assertEqual(parse_requirement_line("pandas[excel]>=2.0 ; python_version>'3.10'", "requirements.txt")["name"], "pandas")
        self.assertIsNone(parse_requirement_line("--extra-index-url https://example.invalid", "requirements.txt"))

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

    def test_pipeline_requires_confirmation_for_global_apply(self) -> None:
        with self.assertRaises(ValueError):
            build_steps(
                python_executable="python",
                apply_global=True,
                confirm_global_write=False,
                reports_dir=Path("reports"),
                master_root=Path("master"),
                backup_base=Path("backups") / "global-sync",
                backup_keep=2,
                retrieval_query="orsi",
                retrieval_status="candidate",
                profile="legacy",
            )

    def test_pipeline_builds_preview_and_apply_steps(self) -> None:
        preview_steps = build_steps(
            python_executable="python",
            apply_global=False,
            confirm_global_write=False,
            reports_dir=Path("reports"),
            master_root=Path("master"),
            backup_base=Path("backups") / "global-sync",
            backup_keep=2,
            retrieval_query="orsi",
            retrieval_status="candidate",
            profile="legacy",
        )
        self.assertIn("--preview", preview_steps[-1].command)
        self.assertFalse(preview_steps[-1].global_write)
        preview_names = [step.name for step in preview_steps]
        self.assertLess(preview_names.index("discover local repositories"), preview_names.index("refresh repository graphs"))
        self.assertLess(preview_names.index("refresh repository graphs"), preview_names.index("harvest clean repositories"))

        apply_steps = build_steps(
            python_executable="python",
            apply_global=True,
            confirm_global_write=True,
            reports_dir=Path("reports"),
            master_root=Path("master"),
            backup_base=Path("backups") / "global-sync",
            backup_keep=2,
            retrieval_query="orsi",
            retrieval_status="candidate",
            profile="legacy",
        )
        publish_steps = [step for step in apply_steps if step.global_write]
        self.assertEqual(len(publish_steps), 1)
        self.assertIn("--apply", publish_steps[0].command)
        self.assertIn("--confirm-global-write", publish_steps[0].command)
        self.assertIn("--backup-keep", publish_steps[0].command)

        optimized_steps = build_steps(
            python_executable="python",
            apply_global=False,
            confirm_global_write=False,
            reports_dir=Path("reports"),
            master_root=Path("master"),
            backup_base=Path("backups") / "global-sync",
            backup_keep=2,
            retrieval_query="orsi",
            retrieval_status="candidate",
            profile="optimized",
        )
        self.assertIn("--profile", optimized_steps[-1].command)
        self.assertIn("optimized", optimized_steps[-1].command)

        optimized_apply_steps = build_steps(
            python_executable="python",
            apply_global=True,
            confirm_global_write=True,
            reports_dir=Path("reports"),
            master_root=Path("master"),
            backup_base=Path("backups") / "global-sync",
            backup_keep=2,
            retrieval_query="orsi",
            retrieval_status="candidate",
            profile="optimized",
        )
        optimized_publish_steps = [step for step in optimized_apply_steps if step.global_write]
        self.assertEqual(len(optimized_publish_steps), 1)
        self.assertIn("--apply", optimized_publish_steps[0].command)
        self.assertIn("optimized", optimized_publish_steps[0].command)

    def test_pipeline_parses_clean_and_dirty_repo_output(self) -> None:
        discovered = parse_discovery_lines(
            [
                "ORSI: branch=main dirty=0 scope=research_training",
                "X_booking: branch=dev02 dirty=2 scope=lead_scraper",
            ]
        )
        self.assertEqual([repo["name"] for repo in discovered if repo["clean"]], ["ORSI"])
        self.assertEqual([repo["name"] for repo in discovered if not repo["clean"]], ["X_booking"])

        harvested = parse_harvest_lines(
            [
                "orsi: skipped (unchanged, candidates=22)",
                "x-booking: blocked_dirty_worktree (uncommitted changes present, candidates=0)",
            ]
        )
        self.assertEqual([repo["id"] for repo in harvested if repo["clean"]], ["orsi"])
        self.assertEqual([repo["id"] for repo in harvested if not repo["clean"]], ["x-booking"])

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
        (cursor / "rules" / "03-stack-catalog.mdc").write_text(
            "# Stack catalog\n\n"
            "| Stack | Packages | Used in | Rule |\n"
            "|-------|----------|---------|------|\n"
            "| Terminal progress | tqdm | All long Python jobs | Required |\n",
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
            cursor_stack = (base / "master" / "cursor" / "rules" / "03-stack-catalog.mdc").read_text(encoding="utf-8")
            config = tomllib.loads((base / "master" / "codex" / "config.toml").read_text(encoding="utf-8"))

            self.assertIn("Preserve this rule", agents)
            self.assertIn("Orchestrator Knowledge Layer", agents)
            self.assertIn("colorama", agents)
            self.assertIn("### tqdm progress bars", skills)
            self.assertIn("### Orchestrator knowledge control plane", skills)
            self.assertIn("colorama", cursor_stack)
            self.assertEqual(config["features"]["memories"], False)
            self.assertIn("workflow_router", config["agents"])
            self.assertTrue((base / "master" / "cursor" / "rules" / "06-orchestrator-knowledge.mdc").exists())
            self.assertIn("codex_agents_sha256", result)

    def test_optimized_synthesis_writes_shadow_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            result = synthesize(
                codex_home=codex,
                cursor_home=cursor,
                master_root=base / "master",
                reports_dir=base / "reports",
                profile="optimized",
            )

            optimized_agents = base / "master" / "optimized" / "codex" / "AGENTS.md"
            optimized_config = base / "master" / "optimized" / "codex" / "config" / "orchestrator-managed.toml"
            optimized_skills = base / "master" / "optimized" / "codex" / "skills-index.md"
            self.assertEqual(result["profile"], "optimized")
            self.assertTrue(optimized_agents.exists())
            self.assertTrue(optimized_skills.exists())
            self.assertTrue(optimized_config.exists())
            self.assertFalse((base / "master" / "codex" / "AGENTS.md").exists())
            self.assertLessEqual(optimized_agents.stat().st_size, 8192)
            self.assertLessEqual(optimized_skills.stat().st_size, 4096)
            self.assertIn("Global Codex instructions", optimized_agents.read_text(encoding="utf-8"))
            self.assertIn("orchestrator-knowledge", optimized_skills.read_text(encoding="utf-8"))
            self.assertNotIn("plugins.", optimized_config.read_text(encoding="utf-8"))
            self.assertTrue((base / "reports" / "repository-compatibility-matrix.md").exists())
            self.assertTrue((base / "reports" / "optimized-config-merge-preview.md").exists())
            self.assertTrue((base / "reports" / "optimized-cutover-plan.md").exists())

    def test_context_budget_audit_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            repo = base / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Repo\n", encoding="utf-8")
            result = audit_context_budget(
                repo_root=repo,
                codex_home=codex,
                cursor_home=cursor,
                master_root=base / "master",
                reports_dir=base / "reports",
            )

            self.assertGreater(result["persistent_estimated_tokens"], 0)
            self.assertTrue((base / "reports" / "context-budget-baseline.md").exists())

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

    def test_optimized_publication_applies_with_backups_and_config_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            before_config = (codex / "config.toml").read_text(encoding="utf-8")
            before_agents = (codex / "AGENTS.md").read_text(encoding="utf-8")
            preview = publish_global_rules(
                reports_dir=base / "reports",
                master_root=base / "master",
                backup_base=base / "backups",
                codex_home=codex,
                cursor_home=cursor,
                profile="optimized",
            )
            self.assertEqual(preview["mode"], "optimized-preview")
            self.assertEqual(before_agents, (codex / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual(before_config, (codex / "config.toml").read_text(encoding="utf-8"))

            with self.assertRaises(RuntimeError):
                publish_global_rules(
                    reports_dir=base / "reports",
                    master_root=base / "master",
                    backup_base=base / "backups",
                    codex_home=codex,
                    cursor_home=cursor,
                    apply=True,
                    profile="optimized",
                )

            applied = publish_global_rules(
                reports_dir=base / "reports",
                master_root=base / "master",
                backup_base=base / "backups",
                codex_home=codex,
                cursor_home=cursor,
                apply=True,
                confirm_global_write=True,
                profile="optimized",
                force_parent_model=True,
            )
            self.assertEqual(applied["mode"], "optimized-applied")
            self.assertTrue((Path(applied["backup_root"]) / "codex" / "AGENTS.md").exists())
            self.assertTrue((Path(applied["legacy_snapshot"]) / "active" / "codex" / "AGENTS.md").exists())
            self.assertIn("Global Codex instructions", (codex / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("Global Codex skills index", (codex / "skills.md").read_text(encoding="utf-8"))
            self.assertIn("[plugins.\"github@openai-curated\"]", (codex / "config.toml").read_text(encoding="utf-8"))
            self.assertIn("workflow_router", tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))["agents"])
            self.assertEqual(tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))["model"], "gpt-5.6-terra")
            self.assertEqual(
                tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))["model_reasoning_effort"],
                "medium",
            )
            self.assertEqual(tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))["agents"]["max_threads"], 4)
            self.assertTrue(tomllib.loads((codex / "config.toml").read_text(encoding="utf-8"))["agents"]["interrupt_message"])
            self.assertTrue((cursor / "rules" / "06-orchestrator-knowledge.mdc").exists())
            self.assertTrue((cursor / "rules" / "07-graphify.mdc").exists())
            self.assertTrue((cursor / "skills" / "lead-scraper" / "SKILL.md").exists())
            self.assertTrue((codex / "skills" / "lead-scraper" / "SKILL.md").exists())

    def test_optimized_synthesis_adds_adaptive_gpt56_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            synthesize(
                codex_home=codex,
                cursor_home=cursor,
                master_root=base / "master",
                reports_dir=base / "reports",
                profile="optimized",
            )

            agents_dir = base / "master" / "optimized" / "codex" / "agents"
            expected = {
                "luna_worker.toml": ("luna_worker", "gpt-5.6-luna", "low"),
                "terra_worker.toml": ("terra_worker", "gpt-5.6-terra", "medium"),
                "sol_specialist.toml": ("sol_specialist", "gpt-5.6-sol", "xhigh"),
            }
            for filename, (name, model, effort) in expected.items():
                with self.subTest(filename=filename):
                    data = tomllib.loads((agents_dir / filename).read_text(encoding="utf-8"))
                    self.assertEqual(data["name"], name)
                    self.assertEqual(data["model"], model)
                    self.assertEqual(data["model_reasoning_effort"], effort)
                    self.assertTrue(data["description"])
                    self.assertTrue(data["developer_instructions"])

            config = tomllib.loads((base / "master" / "optimized" / "codex" / "config" / "orchestrator-managed.toml").read_text(encoding="utf-8"))
            for name in ("workflow_router", "repository_harvester", "knowledge_synthesizer", "verifier", "luna_worker", "terra_worker", "sol_specialist"):
                self.assertIn(name, config["agents"])
            self.assertIn("Adaptive GPT-5.6 Model Routing", (base / "master" / "optimized" / "codex" / "AGENTS.md").read_text(encoding="utf-8"))

    def test_routing_event_validation_rejects_missing_fields_and_sensitive_notes(self) -> None:
        event = {
            "timestamp_utc": "2026-07-10T12:00:00Z",
            "repository": "auto_learning_agent",
            "task_category": "config_migration",
            "risk_level": "high",
            "initial_route": "terra_worker",
            "final_route": "sol_specialist",
            "escalated": True,
            "escalation_reason": "Architecture and rollback review",
            "validation_status": "passed",
            "outcome": "success",
            "reusable_pattern": True,
            "notes": "High-risk model-routing config changes should validate models before global activation.",
        }
        self.assertEqual(validate_routing_event(event), [])

        missing = dict(event)
        missing.pop("timestamp_utc")
        self.assertTrue(any("timestamp_utc" in error for error in validate_routing_event(missing)))

        sensitive = dict(event)
        sensitive["notes"] = "token should not appear here"
        self.assertTrue(any("sensitive" in error for error in validate_routing_event(sensitive)))

    def test_publish_prunes_old_backup_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            codex, cursor = self.write_minimal_global_home(base)
            backup_base = base / "backups"
            for name in ("20260101T000000Z", "20260102T000000Z"):
                old_root = backup_base / name
                old_root.mkdir(parents=True)
                (old_root / "marker.txt").write_text(name, encoding="utf-8")

            applied = publish_global_rules(
                reports_dir=base / "reports",
                master_root=base / "master",
                backup_base=backup_base,
                backup_keep=2,
                codex_home=codex,
                cursor_home=cursor,
                apply=True,
                confirm_global_write=True,
            )

            remaining = sorted(path.name for path in backup_base.iterdir() if path.is_dir())
            self.assertEqual(len(remaining), 2)
            self.assertNotIn("20260101T000000Z", remaining)
            self.assertIn("20260102T000000Z", remaining)
            self.assertIn(Path(applied["backup_root"]).name, remaining)
            self.assertEqual(len(applied["pruned_backups"]), 1)

    def test_optimized_cycle_builds_expected_steps(self) -> None:
        steps = build_optimized_cycle_steps(python_executable="python", reports_dir=Path("reports"), skip_dependency_audit=False)
        names = [step.name for step in steps]
        self.assertLess(names.index("discover repositories"), names.index("refresh repository graphs"))
        self.assertLess(names.index("refresh repository graphs"), names.index("harvest repositories"))
        self.assertEqual(names[0], "discover repositories")
        self.assertIn("audit dependency catalog", names)
        self.assertIn("synthesize optimized instructions", names)

        fast_steps = build_optimized_cycle_steps(python_executable="python", reports_dir=Path("reports"), skip_dependency_audit=True)
        self.assertNotIn("audit dependency catalog", [step.name for step in fast_steps])

    def test_optimized_cutover_builds_dirty_override_cycle_command(self) -> None:
        command = build_cycle_command(
            python_executable="python",
            allow_dirty=True,
            skip_dependency_audit=True,
            verbose=True,
        )
        self.assertEqual(command[:3], ["python", "scripts/run_optimized_knowledge_cycle.py", "--strict"])
        self.assertIn("--continue-on-dirty", command)
        self.assertIn("--skip-dependency-audit", command)
        self.assertIn("--verbose", command)

    def test_retrieve_knowledge_for_repo_resolves_registry_and_inlines_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            registry = base / "repositories.toml"
            registry.write_text(
                "[[repositories]]\n"
                "id = 'demo-repo'\n"
                "name = 'demo'\n"
                f"path = '{repo.as_posix()}'\n"
                "enabled = true\n",
                encoding="utf-8",
            )
            record = sample_candidate_record("demo-repo-repository-profile")
            record["tags"] = ["demo-repo"]
            record_path = base / "knowledge" / "pending" / "demo-repo-repository-profile.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(record), encoding="utf-8")
            catalog = base / "knowledge" / "catalog.jsonl"
            catalog.write_text(
                json.dumps(
                    {
                        "id": record["id"],
                        "title": record["title"],
                        "type": record["type"],
                        "scope": record["scope"],
                        "status": record["status"],
                        "summary": record["summary"],
                        "tags": record["tags"],
                        "record_path": str(record_path),
                        "confidence": record["confidence"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            policy = base / "retrieval-policy.toml"
            policy.write_text("[budgets]\nprimary_records = 3\nsupporting_records = 0\nfailure_records = 0\n", encoding="utf-8")
            context = base / "context.toml"
            context.write_text("maximum_retrieved_records = 3\nmaximum_retrieved_knowledge_estimated_tokens = 4000\n", encoding="utf-8")

            result = retrieve_for_repo(
                cwd=repo,
                repositories_path=registry,
                catalog_path=catalog,
                policy_path=policy,
                context_config_path=context,
                query="",
                status="candidate",
                include_records=True,
                limit=None,
            )

            self.assertEqual(result["repository"]["id"], "demo-repo")
            self.assertEqual(result["count"], 1)
            self.assertIn("verification", result["records"][0])

    def test_repo_hint_propagation_preview_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            agents = repo / "AGENTS.md"
            agents.write_text("# Repo\n", encoding="utf-8")
            registry = base / "repositories.toml"
            registry.write_text(
                "[[repositories]]\n"
                "id = 'demo-repo'\n"
                "name = 'demo'\n"
                f"path = '{repo.as_posix()}'\n"
                "enabled = true\n",
                encoding="utf-8",
            )
            config = base / "context.toml"
            config.write_text("allow_other_repository_writes = false\n", encoding="utf-8")

            result = propagate_hints(
                repositories_path=registry,
                reports_dir=base / "reports",
                config_path=config,
                apply=False,
                confirm_repo_write=False,
            )

            self.assertEqual(result["results"][0]["status"], "preview")
            self.assertNotIn("ORCHESTRATOR-MANAGED: knowledge-retrieval", agents.read_text(encoding="utf-8"))
            self.assertIn("ORCHESTRATOR-MANAGED: knowledge-retrieval", (base / "reports" / "repo-orchestrator-hints-preview.md").read_text(encoding="utf-8"))

    def test_graphify_propagation_preview_is_non_mutating_and_flags_sensitive_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            eligible = base / "eligible"
            sensitive = base / "sensitive"
            eligible.mkdir()
            sensitive.mkdir()
            (eligible / "AGENTS.md").write_text("# Eligible\n", encoding="utf-8")
            (sensitive / "AGENTS.md").write_text("# Sensitive\n", encoding="utf-8")
            registry = base / "repositories.toml"
            registry.write_text(
                "[[repositories]]\n"
                "id = 'eligible'\n"
                f"path = '{eligible.as_posix()}'\n"
                "enabled = true\n"
                "risk_tags = []\n\n"
                "[[repositories]]\n"
                "id = 'sensitive'\n"
                f"path = '{sensitive.as_posix()}'\n"
                "enabled = true\n"
                "risk_tags = ['phi']\n",
                encoding="utf-8",
            )
            config = base / "context.toml"
            config.write_text("allow_other_repository_writes = false\n", encoding="utf-8")

            result = propagate_graphify(
                repositories_path=registry,
                reports_dir=base / "reports",
                config_path=config,
                apply=False,
                confirm_repo_write=False,
            )

            self.assertEqual(result["results"][0]["status"], "preview")
            self.assertEqual(result["results"][1]["status"], "preview")
            self.assertIn("phi", result["results"][1]["risk_tags"])
            self.assertNotIn("graphify-policy", (eligible / "AGENTS.md").read_text(encoding="utf-8"))
            report = (base / "reports" / "graphify-propagation-preview.md").read_text(encoding="utf-8")
            self.assertIn("sensitive", report)

    def test_graphify_policy_block_replacement_is_idempotent(self) -> None:
        first = replace_or_append("# Repo\n", policy_block())
        self.assertEqual(replace_or_append(first, policy_block()), first)

    def test_graphify_version_preflight_and_security_scan(self) -> None:
        self.assertEqual(parse_version("graphify 0.9.12"), (0, 9, 12))
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self.assertEqual(set(preflight_repository(repo)), {"missing-.graphifyignore", "graphify-out-not-ignored"})
            (repo / ".graphifyignore").write_text("\n".join(sorted({".env", ".env.*", "*.key", "*.pem", "data/", "graphify-out/", "*.sqlite"})) + "\n", encoding="utf-8")
            (repo / ".gitignore").write_text("graphify-out/\n", encoding="utf-8")
            self.assertEqual(preflight_repository(repo), [])
            graph = repo / "graph.json"
            graph.write_text(json.dumps({"nodes": [{"id": "x", "source_file": "src/app.py"}], "links": []}), encoding="utf-8")
            self.assertTrue(scan_graph(graph)["passed"])
            first_hash = structural_graph_sha256(graph)
            graph.write_text(json.dumps({"nodes": [{"id": "x", "source_file": "src/app.py", "community": 99}], "links": []}), encoding="utf-8")
            self.assertEqual(structural_graph_sha256(graph), first_hash)
            graph.write_text(json.dumps({"nodes": [{"id": "x", "source_file": "data/private.csv"}], "links": []}), encoding="utf-8")
            self.assertFalse(scan_graph(graph)["passed"])

    def test_federated_merge_uses_registry_ids_and_conservative_import_bridges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inputs = []
            for repo_id in ("repo-a", "repo-b"):
                graph = base / repo_id / "graphify-out" / "graph.json"
                graph.parent.mkdir(parents=True)
                graph.write_text(
                    json.dumps(
                        {
                            "directed": False,
                            "multigraph": False,
                            "graph": {},
                            "nodes": [
                                {"id": "caller", "label": "caller", "file_type": "code"},
                                {"id": "shared", "label": "shared_package", "norm_label": "shared_package", "file_type": "concept"},
                            ],
                            "links": [{"source": "caller", "target": "shared", "relation": "imports"}],
                        }
                    ),
                    encoding="utf-8",
                )
                inputs.append({"id": repo_id, "graph_path": str(graph), "graph_sha256": repo_id, "branch": "main", "commit": repo_id, "dirty": True})
            output = base / "federated" / "graph.json"
            provenance = base / "federated" / "provenance.json"

            summary = merge_graphs(inputs, output, provenance, "graphify 0.9.12")
            merged = json.loads(output.read_text(encoding="utf-8"))
            node_ids = {node["id"] for node in merged["nodes"]}

            self.assertIn("repo::repo-a", node_ids)
            self.assertIn("repo-a::shared", node_ids)
            self.assertTrue(any(node_id.startswith("shared::import::") for node_id in node_ids))
            self.assertEqual(summary["bridge_count"], 1)
            self.assertTrue(all(item["dirty"] for item in summary["inputs"]))

    def test_empty_code_repository_gets_explicit_local_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            graph = write_empty_repository_graph(repo, "docs-only")
            self.assertTrue(graph.exists())
            self.assertTrue((repo / "graphify-out" / "GRAPH_REPORT.md").exists())
            self.assertTrue((repo / "graphify-out" / "graph.html").exists())
            data = json.loads(graph.read_text(encoding="utf-8"))
            self.assertTrue(data["graph"]["empty_code_graph"])

    def test_query_graph_defaults_to_federated_and_builds_scoped_commands(self) -> None:
        self.assertEqual(resolve_graph(scope="federated", repo_id=""), ROOT / "graphify-out" / "federated" / "graph.json")
        self.assertEqual(resolve_graph(scope="local", repo_id=""), ROOT / "graphify-out" / "graph.json")
        command = build_query_command(
            executable=Path("graphify"),
            operation="query",
            values=["architecture"],
            graph=Path("federated.json"),
            budget=750,
        )
        self.assertIn("--graph", command)
        self.assertEqual(command[-2:], ["--budget", "750"])


if __name__ == "__main__":
    unittest.main()
