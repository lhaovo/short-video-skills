from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


@unittest.skipUnless(shutil.which("node"), "node is required")
class DeslopScriptTests(unittest.TestCase):
    def run_node(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["node", str(SCRIPTS / script), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_clean_prose_has_no_blocking_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "story.md"
            source.write_text(
                "林夏把文件放在桌上，问对方是否现在签字。\n"
                "对方没有回答，只把合同翻到最后一页。\n",
                encoding="utf-8",
            )
            result = self.run_node(
                "check-ai-patterns.js",
                "--check",
                "--fail-on=blocking",
                str(source),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_em_dash_is_reported_as_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "story.md"
            source.write_text("她推门——门后站着一个人。\n", encoding="utf-8")
            result = self.run_node(
                "check-ai-patterns.js",
                "--check",
                "--fail-on=blocking",
                str(source),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("em-dash", result.stdout)

    def test_project_whitelist_can_preserve_an_approved_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "story.md"
            source.write_text("她推门——门后站着一个人。\n", encoding="utf-8")
            (Path(tmp) / ".deslop-whitelist").write_text(
                "# 来源：作者要求保留\n她推门——门后站着一个人。\n",
                encoding="utf-8",
            )
            result = self.run_node(
                "check-ai-patterns.js",
                "--check",
                "--fail-on=blocking",
                str(source),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_truncated_text_is_blocking_degeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "story.md"
            source.write_text("她推开门，屋里没有人", encoding="utf-8")
            result = self.run_node(
                "check-degeneration.js",
                "--check",
                "--fail-on=blocking",
                str(source),
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("截断", result.stdout)

    def test_punctuation_check_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "story.md"
            original = "她推门——门后站着一个人。\n"
            source.write_text(original, encoding="utf-8")
            result = self.run_node(
                "normalize-punctuation.js",
                "--check",
                str(source),
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
