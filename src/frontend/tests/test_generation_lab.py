import os
import subprocess
import sys
import unittest
from pathlib import Path

from generation_lab import check_generation


ROOT = Path(__file__).resolve().parents[1]


class GenerationLabTests(unittest.TestCase):
    def run_component(self, mode):
        return subprocess.run(
            [sys.executable, "generation_lab.py", "--check"],
            cwd=ROOT,
            env={**os.environ, "GENERATION_LAB_MODE": mode},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_full_mode_checks_rendered_page(self):
        result = self.run_component("full")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"status": "ok"', result.stdout)
        self.assertIn('"generation_check_completed"', result.stderr)

    def test_basic_mode_changes_check_scope(self):
        self.assertEqual(check_generation("basic")["mode"], "basic")
        self.assertEqual(check_generation("full")["mode"], "full")

    def test_invalid_configuration_fails_with_diagnostic(self):
        result = self.run_component("invalid")
        self.assertEqual(result.returncode, 2)
        self.assertIn("GENERATION_LAB_MODE должен быть basic или full", result.stderr)
        self.assertIn("generation_check_failed", result.stderr)

    def test_version_identifies_source_revision(self):
        result = subprocess.run(
            [sys.executable, "generation_lab.py", "--version"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout.strip(), r"^1\.0\.0\+[0-9a-f]{12}(\+dirty)?$")


if __name__ == "__main__":
    unittest.main()
