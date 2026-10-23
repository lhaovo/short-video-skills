#!/usr/bin/env python3
"""Check the mechanical handoff fields of a short-video storyboard."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHORT = ("镜号", "时长", "这一镜讲什么", "口播", "屏幕文字", "本镜功能")
DETAIL = ("观众认知", "前置依赖", "关键可见事实", "时长意图")
ALIASES = {"观众认知": ("观众认知", "观众此刻应知道什么")}
PLACEHOLDER = re.compile(r"\{\{.*?\}\}")


def blank(value: str, field: str = "") -> bool:
    value = value.strip()
    if not value or PLACEHOLDER.search(value) or value in {"-", "—"}:
        return True
    if value == "无":
        return field != "前置依赖"
    if value.startswith("不适用"):
        reason = re.sub(r"^不适用\s*[:：]?\s*", "", value).strip()
        return len(reason) < 4
    return False


def table_and_details(text: str):
    section = re.search(r"(?ms)^## 四、分镜表\s*$(.*?)(?=^## 五、|\Z)", text)
    if not section:
        raise ValueError("找不到第四节分镜表")
    body = section.group(1)
    lines = body.splitlines()
    table = []
    started = False
    for line in lines:
        if line.lstrip().startswith("|"):
            started = True
            table.append([x.strip() for x in line.strip().strip("|").split("|")])
        elif started:
            break
    if len(table) < 3:
        raise ValueError("分镜表缺表头或数据")
    header = table[0]
    rows = [row for row in table[2:] if row and re.fullmatch(r"\d+", row[0])]
    details = {}
    for match in re.finditer(r"(?ms)^###\s*镜\s*(\d+)\s*$(.*?)(?=^###\s*镜\s*\d+\s*$|^###\s*生成段|\Z)", body):
        fields = {}
        for line in match.group(2).splitlines():
            field = re.match(r"^[-*]\s*([^：:]+)[：:]\s*(.*)$", line)
            if field:
                fields[field.group(1).strip()] = field.group(2).strip()
        details[int(match.group(1))] = fields
    return header, rows, details, len(table) - 2


def parse_target(text: str) -> float | None:
    match = re.search(r"目标时长[：:]\s*(\d+(?:\.\d+)?)\s*(?:s|秒)", text)
    return float(match.group(1)) if match else None


def check(text: str, target: float | None = None) -> dict:
    errors, warnings = [], []
    try:
        header, rows, details, row_count = table_and_details(text)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "shots": 0}
    missing = [name for name in SHORT if name not in header and not (name == "时长" and "时长(s)" in header)]
    if missing:
        errors.append("分镜表缺列：" + "、".join(missing))
    legacy = len(header) in (5, 10) and "时长" in header
    if legacy:
        errors.append(f"旧式 {len(header)} 列分镜表须迁移为六列短表及逐镜详情")
        # 结构错误会导致逐镜详情无法对应；先修格式，再进行逐镜检查。
        return {"ok": False, "errors": errors, "warnings": warnings,
                "shots": len(rows), "total_sec": sum(float(r[1]) for r in rows if len(r) > 1 and re.fullmatch(r"\d+(?:\.\d+)?", r[1])),
                "target_sec": target if target is not None else parse_target(text), "format": f"legacy-{len(header)}"}
    elif len(header) != 6:
        errors.append("短表须有 6 列")
    if not rows:
        errors.append("分镜表没有镜头数据")
    if len(rows) != row_count:
        errors.append("分镜表含非数字镜号或无法解析的数据行")
    seen = []
    total = 0.0
    dependencies = {}
    for row in rows:
        number = int(row[0])
        seen.append(number)
        if len(row) != len(header):
            errors.append(f"镜 {number} 列数 {len(row)} 与表头 {len(header)} 不符")
        values = dict(zip(header, row))
        duration_raw = values.get("时长(s)", values.get("时长", ""))
        duration_match = re.fullmatch(r"\d+(?:\.\d+)?", duration_raw)
        if not duration_match:
            errors.append(f"镜 {number} 时长须填纯数字秒数")
        else:
            duration = float(duration_raw)
            total += duration
            if not 2 <= duration <= 6:
                errors.append(f"镜 {number} 时长 {duration:g}s 超出 2–6s")
        for field in ("这一镜讲什么", "本镜功能"):
            if field not in header:
                continue
            elif blank(values.get(field, ""), field):
                errors.append(f"镜 {number} {field}为空")
        if len(header) == 10:
            item = {key: values.get(next((alias for alias in ALIASES.get(key, (key,)) if alias in header), key), "") for key in DETAIL}
        else:
            item = details.get(number, {})
            if not item:
                errors.append(f"镜 {number} 缺详情块")
        for key in DETAIL:
            value = item.get(key, "")
            if key == "观众认知" and not value:
                value = item.get("观众此刻应知道什么", "")
            if blank(value, key):
                errors.append(f"镜 {number} {key}为空")
        dep = item.get("前置依赖", "")
        refs = [int(x) for x in re.findall(r"(?:镜|S)\s*0*(\d+)\b", dep)]
        if dep and dep != "无" and not dep.startswith("不适用") and not refs:
            errors.append(f"镜 {number} 前置依赖须写镜号或无")
        dependencies[number] = refs
        for ref in refs:
            if ref >= number:
                errors.append(f"镜 {number} 前置依赖镜 {ref} 未早于本镜")
        speech = values.get("口播", "")
        if speech and speech != "无" and not PLACEHOLDER.search(speech):
            count = len(re.findall(r"[\w]", speech, re.UNICODE))
            if count > 36:
                errors.append(f"镜 {number} 口播 {count} 字，超过 36 字")
    if seen != list(range(1, len(seen) + 1)):
        errors.append("镜号须从 1 连续递增，且不得重复")
    for number in details:
        if number not in seen:
            errors.append(f"镜 {number} 详情块没有对应分镜行")
    for number, refs in dependencies.items():
        for ref in refs:
            if ref not in seen:
                errors.append(f"镜 {number} 引用了不存在的镜 {ref}")
    if target is None:
        target = parse_target(text)
    if target is None or target <= 0:
        warnings.append("目标时长未解析；总时长偏差未核对，请用 --target")
    elif abs(total - target) / target > 0.3:
        errors.append(f"分镜总时长 {total:g}s 与目标 {target:g}s 偏差超过 30%")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "shots": len(rows), "total_sec": total, "target_sec": target, "format": f"legacy-{len(header)}" if legacy else "short-6"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--target", type=float)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = check(Path(args.plan).read_text(encoding="utf-8-sig"), args.target)
    except OSError as exc:
        print(f"读不了策划案：{exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"镜头 {result['shots']}，合计 {result.get('total_sec', 0):g}s，格式 {result.get('format', '未知')}")
        for item in result['errors']:
            print("✗ " + item)
        for item in result['warnings']:
            print("! " + item)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
