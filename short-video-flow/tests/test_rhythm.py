import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RHYTHM = ROOT / "scripts" / "check_rhythm.py"
CASE = ROOT.parent / "outputs" / "2026-10-22-丁克大脚丫治插队恶霸"
spec = importlib.util.spec_from_file_location("check_rhythm", RHYTHM)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RhythmTests(unittest.TestCase):
    def test_known_gap_and_speech_density(self):
        srt = ("1\n00:00:01,000 --> 00:00:02,000\n排队！\n\n"
               "2\n00:00:21,130 --> 00:00:22,130\n请继续。\n")
        result = module.analyze(module.parse_srt(srt), 30, 10)
        self.assertAlmostEqual(result["max_gap"]["duration"], 19.13)
        self.assertEqual(result["windows"][1]["chars"], 0)
        self.assertEqual(result["char_count"], 5)

    def test_case_v4_subtitle_reports_actual_gap(self):
        srt = CASE / "05-成片" / "字幕-v4.srt"
        if not srt.exists():
            self.skipTest("ignored real case is not present on this machine")
        args = [sys.executable, str(RHYTHM), "--srt", str(srt), "--dur", "65.57", "--json"]
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.run(args, capture_output=True, env=env)
        report = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual(proc.returncode, 0)
        self.assertAlmostEqual(report["max_gap"]["duration"], 19.13)
        self.assertEqual(report["windows"][1]["chars"], 0)
        self.assertEqual((report["cue_count"], report["char_count"]), (11, 72))
        strict = subprocess.run(args + ["--strict", "--max-gap", "4"], capture_output=True, env=env)
        self.assertEqual(strict.returncode, 2)
