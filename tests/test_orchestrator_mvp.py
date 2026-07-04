from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from harvest_repositories import harvest_repositories  # noqa: E402
from orchestrator_common import retrieve_records, sample_candidate_record, should_audit_file, validate_knowledge_record  # noqa: E402
from publish_global_rules import preview_publication  # noqa: E402


class OrchestratorMvpTests(unittest.TestCase):
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

    def test_harvest_skips_unchanged_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# demo\n", encoding="utf-8")
            state = base / "state" / "repository-snapshots.json"
            pending = base / "pending"
            registry = [{"id": "demo_repo", "path": str(repo), "enabled": True}]

            first = harvest_repositories(registry, state, pending)
            second = harvest_repositories(registry, state, pending)

            self.assertEqual(first[0]["status"], "updated")
            self.assertEqual(second[0]["status"], "skipped")
            self.assertEqual(len(list(pending.glob("*.json"))), 1)
            self.assertIn("demo_repo", json.loads(state.read_text(encoding="utf-8"))["repositories"])

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
