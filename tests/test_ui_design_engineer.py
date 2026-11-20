from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from orchestrator_common import approved_file_path, sha256_file
from publish_global_rules import package_file_plan, publish_global_rules, stage_publication_file
from synthesize_top_level_instructions import (
    AGENT_FILES,
    AGENT_REGISTRATIONS,
    UI_AGENT,
    UI_SKILL,
    UI_SKILL_FILES,
    optimized_skills_index,
    synthesize,
)


class UIDesignEngineerTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.base = Path(workspace.name)
        self.codex = self.base / "codex"
        self.cursor = self.base / "cursor"
        self.codex.mkdir()
        self.cursor.mkdir()
        self.config = self.codex / "config.toml"
        self.before = b'model = "fixture-model"\r\n[agents.user_role]\r\nconfig_file = "user.toml"\r\n'
        self.config.write_bytes(self.before)
        (self.codex / "AGENTS.md").write_text("# Fixture", encoding="utf-8")
        (self.cursor / "keep.md").write_text("Keep", encoding="utf-8")
        self.master = self.base / "master"
        self.reports = self.base / "reports"
        self.backups = self.base / "backups"
        self.skill = self.codex / "skills" / UI_SKILL
        self.agent = self.codex / "agents" / f"{UI_AGENT}.toml"

    def publish(self, **options):
        return publish_global_rules(
            codex_home=self.codex, cursor_home=self.cursor, master_root=self.master,
            reports_dir=self.reports, backup_base=self.backups, profile="optimized",
            ui_design_engineer=True, **options,
        )

    def test_canonical_registration_skill_integrity_and_repeated_synthesis(self) -> None:
        config = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["agents"][UI_AGENT], AGENT_REGISTRATIONS[UI_AGENT])
        agent = tomllib.loads(AGENT_FILES[f"{UI_AGENT}.toml"])
        self.assertEqual(agent["name"], UI_AGENT)
        self.assertTrue({"sandbox_mode", "approval_policy", "model", "model_provider"}.isdisjoint(agent))
        self.assertEqual(list(AGENT_FILES.values()).count(AGENT_FILES[f"{UI_AGENT}.toml"]), 1)

        source = ROOT / ".agents" / "skills" / UI_SKILL
        self.assertEqual({path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()},
                         set(UI_SKILL_FILES))
        entry = (source / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(entry, rf"^---\nname: {UI_SKILL}\ndescription: .+\n---")
        self.assertEqual(set(re.findall(r"\]\(([^)]+)\)", entry)),
                         {relative for relative in UI_SKILL_FILES if relative.startswith("references/")})
        self.assertIn('display_name: "UI Engineer"', (source / "agents/openai.yaml").read_text(encoding="utf-8"))
        self.assertIn(UI_SKILL, optimized_skills_index())
        previous = None
        for _ in range(2):
            synthesize(codex_home=self.codex, cursor_home=self.cursor, master_root=self.master,
                       reports_dir=self.reports, profile="optimized")
            generated = self.master / "optimized"
            fragment = tomllib.loads((generated / "codex/config/orchestrator-managed.toml").read_text(encoding="utf-8"))
            self.assertEqual(fragment["agents"][UI_AGENT], config["agents"][UI_AGENT])
            for relative in UI_SKILL_FILES:
                dest = generated / "agents" / "skills" / UI_SKILL / relative
                self.assertEqual(dest.read_text(encoding="utf-8"), (source / relative).read_text(encoding="utf-8"))
            outputs = [
                generated / "codex" / "agents" / f"{UI_AGENT}.toml",
                generated / "codex/config/orchestrator-managed.toml",
                generated / "codex/skills-index.md",
                *(generated / "agents" / "skills" / UI_SKILL / relative for relative in UI_SKILL_FILES),
            ]
            hashes = [sha256_file(path) for path in outputs]
            if previous:
                self.assertEqual(hashes, previous)
            previous = hashes

    def test_routing_and_write_boundary_contracts(self) -> None:
        router = tomllib.loads(AGENT_FILES["workflow-router.toml"])["developer_instructions"]
        self.assertEqual(router, tomllib.loads(
            (ROOT / ".codex/agents/workflow-router.toml").read_text(encoding="utf-8")
        )["developer_instructions"])
        routing = router.split("16. Recommend ", 1)[1].splitlines()[0]
        positive, negative = routing.split("Leave trivial edits", 1)
        for phrase in ("dashboard redesign", "mobile layout correction", "theme refinement", "component accessibility"):
            self.assertIn(phrase, positive)
        for phrase in ("database migrations", "backend endpoint corrections", "scientific manuscript editing",
                       "authentication policy changes"):
            self.assertIn(phrase, negative)
        policy = tomllib.loads(AGENT_FILES[f"{UI_AGENT}.toml"])["developer_instructions"]
        for phrase in ("Do not spawn agents", "AUDIT and DESIGN are read-only", "IMPLEMENT requires explicit delegation",
                       "inherited workspace write access", "Confirm ownership before editing",
                       "Do not edit authentication, authorization, RLS, migrations",
                       "Escalate cross-boundary work"):
            self.assertIn(phrase, policy)

    def test_preview_apply_and_idempotency_in_fixture_homes(self) -> None:
        preview = self.publish()
        self.assertEqual(preview["plan"], self.publish()["plan"])
        self.assertEqual(len(preview["plan"]), 2 + len(UI_SKILL_FILES))
        self.assertEqual(self.config.read_bytes(), self.before)
        self.assertFalse(self.skill.exists())
        self.assertFalse(self.backups.exists())
        with self.assertRaisesRegex(RuntimeError, "confirm-global-write"):
            self.publish(apply=True)
        outcome = self.publish(apply=True, confirm_global_write=True)
        self.assertTrue(self.config.read_bytes().startswith(self.before))
        self.assertEqual(tomllib.loads(self.config.read_text(encoding="utf-8"))["agents"][UI_AGENT],
                         AGENT_REGISTRATIONS[UI_AGENT])
        backup = Path(outcome["backup_root"]) / "codex"
        rollback = json.loads((backup / "config.toml.registration.json").read_text(encoding="utf-8"))
        self.assertEqual(rollback["prior_bytes"], len(self.before))
        self.assertEqual(rollback["prior_sha256"], hashlib.sha256(self.before).hexdigest())
        self.assertEqual(rollback["published_sha256"], sha256_file(self.config))
        self.assertFalse((backup / "config.toml").exists())
        self.assertTrue((backup / "skills" / UI_SKILL / "SKILL.md.missing").is_file())
        self.assertEqual((self.cursor / "keep.md").read_text(encoding="utf-8"), "Keep")
        self.assertFalse((self.cursor / "skills").exists())
        for item in outcome["applied"]:
            self.assertEqual(sha256_file(Path(item["target"])), item["sha256"])
        second = self.publish(apply=True, confirm_global_write=True)
        self.assertEqual(second["applied"], [])
        self.assertIsNone(second["backup_root"])

    def test_collisions_and_unsafe_paths_fail_before_writes(self) -> None:
        for relative in ("../escape.md", "references/../../escape.md", "C:/escape.md", "references\\escape.md"):
            with self.subTest(relative=relative), self.assertRaisesRegex(RuntimeError, "Unsafe"):
                approved_file_path(self.codex, relative)
        target = self.skill / "references" / "design-brief.md"
        target.parent.mkdir(parents=True)
        target.write_text("User-owned file", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            self.publish()
        self.assertEqual(target.read_text(encoding="utf-8"), "User-owned file")
        self.assertFalse(self.agent.exists())
        self.assertEqual(self.config.read_bytes(), self.before)

        self.agent.parent.mkdir()
        duplicate = self.agent.with_name("user-role.toml")
        duplicate.write_text(f'name = "{UI_AGENT}"', encoding="utf-8")
        target.unlink()
        with self.assertRaisesRegex(RuntimeError, "Duplicate UI Design Engineer"):
            self.publish()
        with self.assertRaisesRegex(RuntimeError, "path collision"):
            package_file_plan([(self.config, target, "first"), (self.config, target, "duplicate")])
        with self.assertRaisesRegex(RuntimeError, "appeared after preview"):
            stage_publication_file(self.config, b"Replacement", replace=False)
        self.assertEqual(self.config.read_bytes(), self.before)

    def test_linked_target_is_rejected(self) -> None:
        outside = self.base / "outside.md"
        outside.write_text("Outside", encoding="utf-8")
        self.skill.mkdir(parents=True)
        try:
            (self.skill / "SKILL.md").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")
        with self.assertRaisesRegex(RuntimeError, "linked publication path"):
            self.publish()
        self.assertEqual(outside.read_text(encoding="utf-8"), "Outside")
