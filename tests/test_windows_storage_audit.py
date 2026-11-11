import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_windows_storage import discover, project_for, safe_walk, size_tree


class StorageAuditTests(unittest.TestCase):
    def test_custom_environment_and_hardlink_without_link_loop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            env = project / "custom-python"
            env.mkdir(parents=True)
            (project / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (env / "pyvenv.cfg").write_text("home = Python\n", encoding="utf-8")
            package = env / "package.bin"
            package.write_bytes(b"12345678")
            os.link(package, project / "cached.bin")
            (env / "unique.bin").write_bytes(b"1234")
            try:
                (env / "loop").symlink_to(project, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            errors = []
            class Progress:
                def update(self, *_args, **_kwargs):
                    pass
            found, disks, development, _ = discover(root, errors, Progress(), 0)
            self.assertEqual(found, [env])
            self.assertEqual(disks, [])
            self.assertEqual(development, [])
            self.assertEqual(project_for(env, root), (project, ["pyproject.toml"]))
            logical, exclusive, linked, _, _ = size_tree(env, errors)
            self.assertEqual(logical, exclusive + linked)
            self.assertGreaterEqual(linked, 8)
            self.assertGreaterEqual(exclusive, 4)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
