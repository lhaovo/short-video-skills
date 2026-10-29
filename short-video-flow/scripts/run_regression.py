#!/usr/bin/env python3
"""Run installed sibling skill regressions with one command."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    test_suites = (
        ("story/deslop", ROOT / "story-deslop" / "tests"),
        ("assets", ROOT / "short-video-assets" / "tests"),
        ("prompt", ROOT / "short-video-prompt" / "tests"),
        ("flow/rhythm", ROOT / "short-video-flow" / "tests"),
    )
    self_tests = (
        ("story", ROOT / "ai-novel-short-story" / "scripts" / "selftest.py"),
        ("drama", ROOT / "short-story-to-drama-storyboard" / "scripts" / "selftest.py"),
    )
    failed = False
    for name, path in test_suites:
        if not path.is_dir():
            print(f"[{name}] SKIP: sibling skill not installed", flush=True)
            continue
        command = [sys.executable, "-m", "unittest", "discover", "-s", str(path), "-v"]
        result = subprocess.run(command, cwd=ROOT, check=False)
        print(f"[{name}] {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
        failed |= result.returncode != 0
    for name, path in self_tests:
        if not path.is_file():
            print(f"[{name}] SKIP: sibling skill not installed", flush=True)
            continue
        result = subprocess.run([sys.executable, str(path)], cwd=ROOT, check=False)
        print(f"[{name}] {'PASS' if result.returncode == 0 else 'FAIL'}", flush=True)
        failed |= result.returncode != 0
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
