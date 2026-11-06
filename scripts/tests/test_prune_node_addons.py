import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRUNE = ROOT / "scripts" / "prune-node-addons.py"


class PruneNodeAddonsTests(unittest.TestCase):
    def test_glibc_target_removes_musl_native_addons_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            addons = root / "node_modules" / "@msgpackr-extract"
            addons.mkdir(parents=True)
            musl = addons / "node.abi115.musl.node"
            glibc = addons / "node.abi115.glibc.node"
            other = addons / "README.md"
            for path in (musl, glibc, other):
                path.write_text(path.name)

            subprocess.run([sys.executable, str(PRUNE), "glibc", str(root)], check=True)

            self.assertFalse(musl.exists())
            self.assertTrue(glibc.exists())
            self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
