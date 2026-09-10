import json
import tempfile
import unittest
from pathlib import Path

from casp.caspian_config import build_files_index

from src.runtime.file_index import refresh_file_index


class FileIndexTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.index = self.root / "settings/files-list.json"
        self.add_file("src/app/index.py")
        self.add_file("src/app/layout.py")

    def add_file(self, name, content=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read_index(self):
        return json.loads(self.index.read_text(encoding="utf-8"))

    def test_new_generation_route_replaces_stale_inventory(self):
        refresh_file_index(self.root)
        self.add_file("src/app/generation/index.py")
        self.add_file("public/css/pages/generation.css")
        self.assertNotIn("./src/app/generation/index.py", self.read_index())

        refresh_file_index(self.root)

        routes = build_files_index(self.read_index()).routes
        self.assertIn("/generation", [route.fastapi_rule for route in routes])
        self.assertIn("./public/css/pages/generation.css", self.read_index())

    def test_deleted_routes_are_removed_after_branch_switch(self):
        self.add_file("src/app/profile/index.py")
        refresh_file_index(self.root)
        (self.root / "src/app/profile/index.py").unlink()

        refresh_file_index(self.root)

        self.assertNotIn("./src/app/profile/index.py", self.read_index())

    def test_missing_or_invalid_index_is_rebuilt(self):
        refresh_file_index(self.root)
        self.assertIn("./src/app/index.py", self.read_index())
        self.index.write_text("{", encoding="utf-8")
        refresh_file_index(self.root)
        self.assertIn("./src/app/index.py", self.read_index())

    def test_current_inventory_is_not_rewritten(self):
        refresh_file_index(self.root)
        before = self.index.stat().st_mtime_ns
        refresh_file_index(self.root)
        self.assertEqual(before, self.index.stat().st_mtime_ns)

    def test_python_cache_is_excluded(self):
        self.add_file("src/app/__pycache__/index.cpython-314.pyc")
        self.add_file("public/example.pyc")
        refresh_file_index(self.root)
        self.assertEqual(
            self.read_index(), ["./src/app/index.py", "./src/app/layout.py"]
        )


if __name__ == "__main__":
    unittest.main()
