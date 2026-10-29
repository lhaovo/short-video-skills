import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check_assets.py"


class AssetRuleTests(unittest.TestCase):
    def test_single_anchor_image_passes_without_candidate_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "02-资产清单.md").write_text(
                "| 编号 | 类型 | 用途 | 来源 | 被哪些段引用 | 状态 |\n"
                "|---|---|---|---|---|---|\n"
                "| PR-01 | 产品主体 | 产品主图 | AI | S01 | 已有 |\n",
                encoding="utf-8",
            )
            image_dir = root / "04-素材" / "01-资产图"
            image_dir.mkdir(parents=True)
            (image_dir / "PR-01_产品主图_v1.png").write_bytes(b"not-a-real-image")

            result = subprocess.run(
                [sys.executable, str(CHECK), "--dir", str(root), "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, report)
            self.assertFalse(any("A5" in warning for warning in report["warn"]))

    def test_candidate_sheet_check_is_removed(self):
        result = subprocess.run(
            [sys.executable, str(CHECK), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--sheet", result.stdout)
        self.assertNotIn("候选数", result.stdout)


if __name__ == "__main__":
    unittest.main()
