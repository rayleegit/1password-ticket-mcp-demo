"""Package tests use isolated fixtures, never actual local credentials."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from package_mcp import FILES, create_package


class PackageTests(unittest.TestCase):
    def populate(self, root: Path) -> None:
        for name in FILES:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("synthetic source fixture\n")

    def test_only_allowlisted_files_are_packaged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            for name in (".cursor/mcp.json", ".env", ".env.demo", "verification/local.json",
                         "demo.py", "presentation/private-notes.txt"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("synthetic excluded fixture")
            output = root / "source.zip"
            create_package(output, root)
            with ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), {f"ticket-mcp-demo/{n}" for n in FILES})
                self.assertIsNone(archive.testzip())

    def test_missing_file_prevents_package(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                create_package(root / "source.zip", root)
            self.assertFalse((root / "source.zip").exists())

    def test_symlink_prevents_package(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.populate(root)
            target = root / FILES[0]
            # Exercise rejection without requiring Windows symlink privileges.
            with patch.object(Path, "is_symlink", autospec=True,
                              side_effect=lambda path: path == target), self.assertRaises(ValueError):
                create_package(root / "source.zip", root)
            self.assertFalse((root / "source.zip").exists())
