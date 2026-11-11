import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_windows_drive import GIB, candidate_kind, category, scan, write_reports
from audit_windows_storage import safe_walk


class DriveAuditTests(unittest.TestCase):
    def test_categories_and_hardlinks_reconcile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "Users" / "Alice" / "Documents" / "GitHub" / "project" / ".venv"
            cache = root / "Users" / "Alice" / "AppData" / "Local" / "uv" / "cache"
            project.mkdir(parents=True)
            cache.mkdir(parents=True)
            (project / "pyvenv.cfg").write_bytes(b"home")
            package = cache / "package.bin"
            package.write_bytes(b"12345678")
            os.link(package, project / "package.bin")
            system = root / "Windows"
            system.mkdir()
            (system / "kernel.bin").write_bytes(b"123")
            downloads = root / "Users" / "Alice" / "Downloads"
            downloads.mkdir()
            (downloads / "video.bin").write_bytes(b"12345")
            (downloads / "disk.vhdx").write_bytes(b"123456")
            try:
                (project / "loop").symlink_to(root, target_is_directory=True)
            except (OSError, NotImplementedError):
                pass
            result = scan(root, Console(file=io.StringIO(), force_terminal=False))
            self.assertEqual(result["logical"], 4 + 8 + 8 + 3 + 5 + 6)
            self.assertEqual(result["unique"], result["logical"] - 8)
            self.assertEqual(result["single"], result["logical"] - 16)
            self.assertEqual(sum(row[0] for row in result["categories"].values()), result["logical"])
            self.assertEqual(result["categories"]["Virtual disks"][0], 6)
            self.assertEqual(result["categories"]["Personal files"][0], 5)
            self.assertEqual(result["categories"]["Windows and system"][0], 3)
            self.assertIn(project, result["candidates"])
            result["folders"][root / "Users" / "Alice" / "AppData" / "Local" / "Google"] = [6 * GIB, 6 * GIB, 1, time.time()]
            report, inventory = write_reports(result, root / "reports")
            self.assertIn("Difference between drive used", report.read_text(encoding="utf-8"))
            self.assertIn("Identify the owning app", report.read_text(encoding="utf-8"))
            self.assertTrue(inventory.exists())

    def test_inaccessible_path_is_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            denied = root / "denied"
            denied.mkdir()
            real_scandir = os.scandir

            def guarded(path):
                if Path(path) == denied:
                    raise PermissionError(13, "Access denied", str(path))
                return real_scandir(path)

            with mock.patch("os.scandir", side_effect=guarded):
                found = list(safe_walk(root, errors := []))
            self.assertEqual(len(found), 1)
            self.assertEqual(len(errors), 1)
            self.assertIn("denied", errors[0])

    def test_category_rules(self):
        self.assertEqual(category(Path("pagefile.sys")), "Windows and system")
        self.assertEqual(category(Path("Program Files") / "App" / "data"), "Installed software")
        self.assertEqual(category(Path("Users") / "Alice" / "Documents" / "GitHub" / "repo" / "src.py"), "Development")
        self.assertEqual(category(Path("Users") / "Alice" / "Videos" / "vm.vhdx"), "Virtual disks")
        root = Path("C:\\")
        self.assertEqual(candidate_kind(root / "Users" / "Alice" / "Documents" / "GitHub" / "repo" / "node_modules", root, set()), "Generated project files")
        self.assertIsNone(candidate_kind(root / "Users" / "Alice" / "AppData" / "Local" / "nvm" / "v24" / "node_modules", root, set()))


if __name__ == "__main__":
    unittest.main()
