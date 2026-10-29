#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enforce forward-only stage order for a short-video production directory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STAGES = ("S1A", "S1B", "S2", "S3", "S4", "S5", "已完成")
GATES_FOR_ENTRY = {
    "S1A": (),
    "S1B": ("G1-A",),
    "S2": ("G1-A", "G1-B"),
    "S3": ("G1-A", "G1-B", "G2"),
    "S4": ("G1-A", "G1-B", "G2", "G3"),
    "S5": ("G1-A", "G1-B", "G2", "G3", "G4"),
    "已完成": ("G1-A", "G1-B", "G2", "G3", "G4", "G5"),
}
ENTRY_ARTIFACTS = {
    "S1A": (),
    "S1B": ("01-故事/story.md",),
    "S2": ("01-故事/drama/storyboard.md",),
    "S3": ("02-资产清单.md", "03-生成清单.md"),
    "S4": ("04-素材/03-片段",),
    "S5": ("05-成片",),
    "已完成": ("06-发布包.md",),
}
def normalized(value: str) -> str:
    return value.replace("*", "").replace("`", "").replace("{{", "").replace("}}", "").strip()


def parse_state(path: Path) -> tuple[str, dict[str, set[str]]]:
    current = ""
    gate_values: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        raw_cells = line.strip().strip("|").split("|")
        cells = [normalized(cell) for cell in raw_cells]
        if len(cells) < 2:
            continue
        key = cells[0]
        if key == "当前阶段":
            if "{{" in raw_cells[1]:
                continue
            candidate = next((stage for stage in STAGES if stage in cells[1]), "")
            if candidate:
                current = candidate
        elif key.startswith("G") and len(cells) >= 3:
            gate_values.setdefault(key, set()).add(cells[2])
    return current, gate_values


def gate_passed(gates: dict[str, set[str]], name: str) -> bool:
    values = gates.get(name, set())
    return any(value in {"通过", "过"} for value in values)


def artifact_present(base: Path, relative: str) -> bool:
    path = base / relative
    if path.is_file():
        return True
    if not path.is_dir():
        return False
    if relative in {"04-素材/03-片段", "05-成片"}:
        return any(path.glob("*.mp4"))
    return True


def check(base: Path, enter: str) -> dict:
    state_path = base / "00-流程状态.md"
    errors: list[str] = []
    if not state_path.is_file():
        return {"ok": False, "current": "", "enter": enter, "errors": ["缺少 00-流程状态.md"]}

    current, gates = parse_state(state_path)
    if current not in STAGES:
        errors.append("当前阶段必须明确填写 S1A / S1B / S2 / S3 / S4 / S5 / 已完成")
        return {"ok": False, "current": current, "enter": enter, "errors": errors}
    if enter not in STAGES:
        errors.append(f"未知目标阶段：{enter}")
        return {"ok": False, "current": current, "enter": enter, "errors": errors}

    current_index = STAGES.index(current)
    enter_index = STAGES.index(enter)
    skipped = enter_index > current_index + 1
    went_back = enter_index < current_index
    if skipped:
        errors.append(f"禁止跳步：当前 {current}，不能直接进入 {enter}")
    if went_back:
        errors.append(f"禁止静默回退：当前 {current}，不能直接进入更早的 {enter}；先显式重置后续门禁")

    required_gates = GATES_FOR_ENTRY[enter]
    for required_gate in required_gates:
        if not gate_passed(gates, required_gate):
            errors.append(f"进入 {enter} 前必须通过 {required_gate}")

    if enter_index == current_index + 1:
        for relative in ENTRY_ARTIFACTS[enter]:
            if not artifact_present(base, relative):
                errors.append(f"进入 {enter} 前缺少必备产物：{relative}")

    return {
        "ok": not errors,
        "current": current,
        "enter": enter,
        "required_gates": list(required_gates),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查短视频制作是否按 S1A→S1B→S2→S3→S4→S5 顺序推进")
    parser.add_argument("--dir", required=True, help="制作目录")
    parser.add_argument("--enter", required=True, choices=STAGES, help="即将进入的阶段")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = check(Path(args.dir).expanduser().resolve(), args.enter)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"当前阶段：{result['current'] or '未识别'} ｜ 即将进入：{result['enter']}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"  ✗ {error}")
            print("结论：禁止推进，先补齐当前阶段")
        else:
            print("结论：允许进入")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
