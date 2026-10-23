"""End-to-end regression checks for the gate scripts and the recorded v4 subtitle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "check_gen_list.py"
FIELDS = ("主体", "状态", "动作", "环境", "光线", "景别", "机位/角度", "运镜", "依赖/可见事实")


def generation(body):
    return """# 生成清单
## 一、概览
| 段号 | 镜号 | 时长 | 模式 | 引用素材 | 首帧 | 前置依赖/关键事实 |
|---|---|---:|---|---|---|---|
| S01 | 1 | 4 | 文生 | 无 | 无 | 无；建立队伍在店门口 |
## 二、逐段提示词
### S01 · 镜 1
""" + body + "\nMotion: camera stays still.\nNo subtitles.\n"


class GateCliTests(unittest.TestCase):
    def run_gen(self, body, target=True):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "03-生成清单.md"
            source.write_text(generation(body), encoding="utf-8")
            args = [sys.executable, str(GEN), "--gen", str(source), "--json"]
            if target:
                args += ["--target", "4"]
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            proc = subprocess.run(args, capture_output=True, env=env)
            return proc.returncode, json.loads(proc.stdout.decode("utf-8"))

    def test_structured_nonempty_fields_pass(self):
        table = "| 画面字段 | 本段描述 |\n|---|---|\n" + "\n".join(
            f"| {field} | {'无' if field == '依赖/可见事实' else '清楚描述'} |" for field in FIELDS
        )
        code, report = self.run_gen(table)
        self.assertEqual(code, 0, report)
        self.assertTrue(report["ok"])

    def test_empty_table_and_placeholder_table_fail(self):
        for value in ("", "{{待填}}"):
            with self.subTest(value=value):
                table = "| 画面字段 | 本段描述 |\n|---|---|\n" + "\n".join(
                    f"| {field} | {value} |" for field in FIELDS
                )
                code, report = self.run_gen(table)
                self.assertEqual(code, 2)
                self.assertIn("值空：主体", " ".join(report["fatal"]))

    def test_prose_and_missing_segment_fail(self):
        code, report = self.run_gen("主体状态动作环境光线景别机位/角度运镜。")
        self.assertEqual(code, 2)
        self.assertIn("缺画面字段表", " ".join(report["fatal"]))
        code, report = self.run_gen("", target=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("目标时长未解析" in warning for warning in report["warn"]))

    def test_missing_and_extra_sections_fail_f5(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "03-生成清单.md"
            source.write_text(generation("").replace("### S01 · 镜 1", "### S02 · 镜 1"), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(GEN), "--gen", str(source), "--target", "4", "--json"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            report = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(proc.returncode, 2)
            self.assertTrue(all("[F5]" in item for item in report["fatal"]))

    def test_missing_handoff_column_fails_f8(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "03-生成清单.md"
            source.write_text(generation("").replace(" | 前置依赖/关键事实 |", " |").replace("|---|---|---:|---|---|---|---|", "|---|---|---:|---|---|---|"), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(GEN), "--gen", str(source), "--target", "4", "--json"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            report = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("[F8]", " ".join(report["fatal"]))

    def test_only_no_handoff_reports_precise_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "03-生成清单.md"
            source.write_text(generation("").replace("无；建立队伍在店门口", "无"), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(GEN), "--gen", str(source), "--target", "4", "--json"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            report = json.loads(proc.stdout.decode("utf-8"))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("只写了无，须补本段关键可见事实", " ".join(report["fatal"]))

if __name__ == "__main__":
    unittest.main()
