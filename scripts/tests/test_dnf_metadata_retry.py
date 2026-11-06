import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "dnf-install-with-metadata-retry.sh"


class DnfMetadataRetryTests(unittest.TestCase):
    def run_helper(self, mode):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_dnf = root / "dnf"
            calls = root / "calls"
            fake_dnf.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >> \"$DNF_CALLS\"\n"
                "if [ \"$1\" = clean ]; then exit 0; fi\n"
                "attempt=$(grep -c '^install ' \"$DNF_CALLS\" || true)\n"
                "case \"$DNF_MOCK_MODE\" in\n"
                "  transient-once) [ \"$attempt\" -gt 1 ] && exit 0; "
                "    echo \"Failed to download metadata for repo 'epel': Cannot download repomd.xml\" >&2; exit 1 ;;\n"
                "  transient-always) echo \"Checksum doesn't match for repo 'epel'\" >&2; exit 1 ;;\n"
                "  package-error) echo 'No match for argument: missing-package' >&2; exit 1 ;;\n"
                "esac\n"
            )
            fake_dnf.chmod(0o755)
            env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", DNF_CALLS=str(calls), DNF_MOCK_MODE=mode)
            result = subprocess.run(
                [str(HELPER), "install", "-y", "example"],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            return result, calls.read_text() if calls.exists() else ""

    def test_retries_epel_metadata_failure_after_cleaning_metadata(self):
        result, calls = self.run_helper("transient-once")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.splitlines(), ["install -y example", "clean metadata", "install -y example"])

    def test_stops_after_three_metadata_failures(self):
        result, calls = self.run_helper("transient-always")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.splitlines(), [
            "install -y example", "clean metadata",
            "install -y example", "clean metadata",
            "install -y example",
        ])
        self.assertIn("Checksum doesn't match", result.stdout + result.stderr)

    def test_does_not_retry_non_metadata_package_errors(self):
        result, calls = self.run_helper("package-error")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls.splitlines(), ["install -y example"])
        self.assertIn("No match for argument", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
