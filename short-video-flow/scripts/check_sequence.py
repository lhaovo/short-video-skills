#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enforce ordered stages and explicit user approval at every gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STAGES = ("S1A", "S1B", "S2", "S3", "S4", "S5", "已完成")
GATES_FOR_ENTRY = {
    "S1A": (),
    "S1B": ("G1-A",),
    "S2": ("G1-A", "G1-B"),
    "S3": ("G1-A", "G1-B", "G2"),
    "S4": ("G1-A", "G1-B", "G2", "G3-A", "G3"),
    "S5": ("G1-A", "G1-B", "G2", "G3-A", "G3", "G4"),
    "已完成": ("G1-A", "G1-B", "G2", "G3-A", "G3", "G4", "G5"),
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
APPROVED = "已批准"
GATE_STAGE = {
    "G1-A": "S1A",
    "G1-B": "S1B",
    "G2": "S2",
    "G3-A": "S3",
    "G3": "S3",
    "G4": "S4",
    "G5": "S5",
}


def normalized(value: str) -> str:
    return value.replace("*", "").replace("`", "").replace("{{", "").replace("}}", "").strip()


def markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    tables = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        block = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            block.append(lines[index])
            index += 1
        raw_rows = [line.strip().strip("|").split("|") for line in block]
        rows = [[normalized(cell) for cell in row] for row in raw_rows]
        rows = [
            row for row in rows
            if not all(cell and set(cell) <= {"-", ":"} for cell in row)
        ]
        if len(rows) >= 2:
            tables.append((rows[0], rows[1:]))
    return tables


def parse_state(path: Path) -> tuple[str, dict[str, dict[str, str]]]:
    text = path.read_text(encoding="utf-8")
    current = ""
    gates: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        raw_cells = line.strip().strip("|").split("|")
        if len(raw_cells) >= 2 and normalized(raw_cells[0]) == "当前阶段":
            if "{{" in raw_cells[1]:
                return "", gates
    for header, rows in markdown_tables(text):
        if "项" in header and "内容" in header:
            content_index = header.index("内容")
            for row in rows:
                if row and row[0] == "当前阶段":
                    value_index = min(content_index, len(row) - 1)
                    value = row[value_index]
                    candidate = next((stage for stage in STAGES if stage in value), "")
                    if candidate:
                        current = candidate
        if "门" not in header:
            continue
        status_index = header.index("门禁状态") if "门禁状态" in header else (
            header.index("结果") if "结果" in header else None
        )
        evidence_index = next(
            (i for i, name in enumerate(header) if "批准版本" in name),
            None,
        )
        if status_index is None:
            continue
        for row in rows:
            if not row or not row[0].startswith("G"):
                continue
            gates[row[0]] = {
                "status": row[status_index] if status_index < len(row) else "",
                "evidence": row[evidence_index] if evidence_index is not None and evidence_index < len(row) else "",
            }
    return current, gates


def gate_reason(gates: dict[str, dict[str, str]], name: str) -> str | None:
    item = gates.get(name)
    if not item:
        return f"缺少门禁记录 {name}"
    if item["status"] != APPROVED:
        return f"{name} 当前为「{item['status'] or '未填写'}」，只有「{APPROVED}」才能推进"
    if not item["evidence"] or item["evidence"] in {"-", "—", "待填", "无"}:
        return f"{name} 已批准但缺少批准版本或授权范围"
    return None


def artifact_present(base: Path, relative: str) -> bool:
    path = base / relative
    if path.is_file():
        return True
    if not path.is_dir():
        return False
    if relative in {"04-素材/03-片段", "05-成片"}:
        return any(path.glob("*.mp4"))
    return True


def check_stage(base: Path, enter: str) -> dict:
    state_path = base / "00-流程状态.md"
    if not state_path.is_file():
        return {"ok": False, "current": "", "enter": enter, "errors": ["缺少 00-流程状态.md"]}
    current, gates = parse_state(state_path)
    errors: list[str] = []
    if current not in STAGES:
        errors.append("当前阶段必须明确填写 S1A / S1B / S2 / S3 / S4 / S5 / 已完成")
        return {"ok": False, "current": current, "enter": enter, "errors": errors}
    if enter not in STAGES:
        errors.append(f"未知目标阶段：{enter}")
        return {"ok": False, "current": current, "enter": enter, "errors": errors}

    current_index = STAGES.index(current)
    enter_index = STAGES.index(enter)
    if enter_index > current_index + 1:
        errors.append(f"禁止跳步：当前 {current}，不能直接进入 {enter}")
    if enter_index < current_index:
        errors.append(f"禁止静默回退：当前 {current}，不能直接进入更早的 {enter}")

    for name in GATES_FOR_ENTRY[enter]:
        reason = gate_reason(gates, name)
        if reason:
            errors.append(reason)

    if enter_index == current_index + 1:
        for relative in ENTRY_ARTIFACTS[enter]:
            if not artifact_present(base, relative):
                errors.append(f"进入 {enter} 前缺少必备产物：{relative}")
    return {
        "ok": not errors,
        "current": current,
        "enter": enter,
        "required_gates": list(GATES_FOR_ENTRY[enter]),
        "errors": errors,
    }


def check_gate(base: Path, name: str) -> dict:
    state_path = base / "00-流程状态.md"
    if not state_path.is_file():
        return {"ok": False, "gate": name, "errors": ["缺少 00-流程状态.md"]}
    current, gates = parse_state(state_path)
    errors = []
    expected_stage = GATE_STAGE.get(name)
    if expected_stage and current != expected_stage:
        errors.append(f"{name} 只能在 {expected_stage} 检查，当前阶段为 {current or '未识别'}")
    reason = gate_reason(gates, name)
    if reason:
        errors.append(reason)
    return {
        "ok": not errors,
        "current": current,
        "gate": name,
        "record": gates.get(name),
        "errors": errors,
    }


def print_result(result: dict) -> None:
    target = result.get("enter") or result.get("gate")
    if result.get("current") is not None:
        print(f"当前阶段：{result.get('current') or '未识别'} ｜ 检查：{target}")
    else:
        print(f"检查：{target}")
    if result["errors"]:
        for error in result["errors"]:
            print(f"  ✗ {error}")
        print("结论：禁止推进")
    else:
        print("结论：允许推进")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查阶段顺序、用户批准状态和前置产物")
    parser.add_argument("--dir", required=True, help="制作目录")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--enter", choices=STAGES, help="即将进入的阶段")
    target.add_argument("--gate", help="只检查指定门禁，例如 G3-A")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    base = Path(args.dir).expanduser().resolve()
    result = check_stage(base, args.enter) if args.enter else check_gate(base, args.gate)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_result(result)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
