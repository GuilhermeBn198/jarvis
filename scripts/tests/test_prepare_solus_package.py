import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "scripts" / "prepare-solus-package.py"
TEMPLATE = ROOT / "packaging" / "solus" / "package.yml"


class PrepareSolusPackageTests(unittest.TestCase):
    def test_default_render_keeps_first_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "source.tar.gz"
            archive.write_bytes(b"solus default fixture")
            output = root / "package.yml"
            subprocess.run([sys.executable, str(PREPARE), str(TEMPLATE), str(archive), str(output)], check=True)
            self.assertIn("release    : 1", output.read_text())

    def test_release_override_generates_distinct_revision_with_local_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "source.tar.gz"
            archive.write_bytes(b"solus upgrade fixture")
            output = root / "package.yml"

            subprocess.run(
                [sys.executable, str(PREPARE), str(TEMPLATE), str(archive), str(output), "--release", "2"],
                check=True,
            )

            rendered = output.read_text()
            self.assertIn("release    : 2", rendered)
            self.assertIn(archive.resolve().as_uri(), rendered)
            self.assertIn(hashlib.sha256(archive.read_bytes()).hexdigest(), rendered)
            self.assertNotIn("@JARVIS_SOURCE_", rendered)

    def test_release_override_must_be_positive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "source.tar.gz"
            archive.write_bytes(b"solus invalid fixture")
            result = subprocess.run(
                [sys.executable, str(PREPARE), str(TEMPLATE), str(archive), str(root / "package.yml"), "--release", "0"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("positive integer", result.stdout)

    def test_package_builder_rejects_release_override_for_non_solus_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [str(ROOT / "scripts" / "build-package.sh"), "--target", "arch", "--arch", "x86_64",
                 "--release", "2", "--output", temp],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--release so e valido para o alvo solus", result.stdout)


if __name__ == "__main__":
    unittest.main()
