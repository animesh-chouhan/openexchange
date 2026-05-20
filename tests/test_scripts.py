import subprocess
import unittest
from pathlib import Path


class ScriptSyntaxTest(unittest.TestCase):
    def test_shell_scripts_parse(self):
        repo_root = Path(__file__).resolve().parents[1]
        scripts = [
            "run.sh",
            "setup.sh",
            "update.sh",
            "scripts/run.sh",
            "scripts/setup.sh",
            "scripts/update.sh",
            "deploy/config.sh",
        ]

        result = subprocess.run(
            ["bash", "-n", *scripts],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
