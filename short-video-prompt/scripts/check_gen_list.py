#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成清单校验：结构、时长、资产与逐段画面字段。

用法：
    python check_gen_list.py --dir <制作目录>
    python check_gen_list.py --gen 03-生成清单.md --assets 02-资产清单.md --target 30

退出码：0 通过 / 2 存在致命项 / 3 输入无法解析
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ASSET_ID = re.compile(r"(?:PR|SC|CH|SP)-\d{2}[A-Z]?", re.I)
SEG_HEADING = re.compile(r"^#{2,4}\s*(S\d{2})\b", re.M)
TOLERANCE_SEC = 1.0
MIN_SEG, MAX_SEG = 2.0, 10.0
TABLE_FIELDS = (
    "主体", "状态", "动作", "环境", "光线", "景别", "机位/角度", "运镜", "依赖/可见事实"
)


def split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_sep_row(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def parse_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """返回 [(表头, 数据行)]，按出现顺序。"""
    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [split_row(b) for b in block]
            rows = [r for r in rows if r and not is_sep_row(r)]
            if len(rows) >= 2:
                tables.append((rows[0], rows[1:]))
        else:
            i += 1
    return tables


def find_field_table(body: str) -> dict[str, str] | None:
    for header, rows in parse_tables(body):
        if not header or header[0].strip() != "画面字段":
            continue
        values = {}
        for row in rows:
            if len(row) >= 2 and row[0].strip():
                key = re.sub(r"\*\*", "", row[0]).strip()
                values[key] = row[1].strip()
        return values or None
    return None


def is_blank(value: str, field: str) -> bool:
    if re.search(r"\{\{.*?\}\}", value or ""):
        return True
    text = re.sub(r"\{\{.*?\}\}", "", value or "").replace("**", "").strip()
    if not text or text in {"-", "—"}:
        return True
    if text == "无":
        return field != "依赖/可见事实"
    if text.startswith("不适用"):
        reason = re.sub(r"^不适用\s*[:：]?\s*", "", text).strip()
        return len(reason) < 4
    return len(text) < 2


def col_index(header: list[str], *keywords: str) -> int | None:
    for idx, name in enumerate(header):
        for kw in keywords:
            if kw in name:
                return idx
    return None


def get(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def to_float(text: str) -> float | None:
    m = re.search(r"-?\d+(?:\.\d+)?", text or "")
    return float(m.group()) if m else None


def find_asset_table(tables):
    for header, rows in tables:
        if col_index(header, "编号") is not None and col_index(header, "类型") is not None:
            return header, rows
    return None, None


def find_gen_table(tables):
    for header, rows in tables:
        if col_index(header, "段号") is not None and col_index(header, "镜号") is not None:
            return header, rows
    return None, None


def parse_target_from_plan(path: Path) -> float | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    patterns = [
        r"目标时长[：:]\s*(\d+(?:\.\d+)?)\s*s",
        r"目标时长[^\n]{0,12}?(\d+(?:\.\d+)?)\s*秒",
        r"总时长[：:]\s*(\d+(?:\.\d+)?)\s*s",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return float(m.group(1))
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="生成清单机械字段校验")
    ap.add_argument("--dir", help="制作目录（含 02-资产清单.md 与 03-生成清单.md）")
    ap.add_argument("--gen", help="生成清单路径")
    ap.add_argument("--assets", help="资产清单路径")
    ap.add_argument("--target", type=float, help="分镜总时长（秒）")
    ap.add_argument("--plan", help="策划案路径，用于读取目标时长")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.dir:
        base = Path(args.dir)
        gen_path = Path(args.gen) if args.gen else base / "03-生成清单.md"
        asset_path = Path(args.assets) if args.assets else base / "02-资产清单.md"
        plan_path = Path(args.plan) if args.plan else base / "01-策划案.md"
    else:
        if not args.gen:
            print("缺少输入：用 --dir 或 --gen 指定生成清单", file=sys.stderr)
            return 3
        gen_path = Path(args.gen)
        asset_path = Path(args.assets) if args.assets else None
        plan_path = Path(args.plan) if args.plan else None

    if not gen_path.exists():
        print(f"读不了生成清单：{gen_path}", file=sys.stderr)
        return 3

    try:
        gen_text = gen_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不了生成清单：{exc}", file=sys.stderr)
        return 3

    asset_text = ""
    if asset_path and asset_path.exists():
        try:
            asset_text = asset_path.read_text(encoding="utf-8")
        except OSError:
            asset_text = ""

    target = args.target
    if target is None and plan_path and plan_path.exists():
        target = parse_target_from_plan(plan_path)

    fatal: list[str] = []
    warn: list[str] = []
    info: dict = {"file": str(gen_path), "segments": 0, "total_sec": 0.0, "target": target}

    # ---- 解析切段表 ----
    header, rows = find_gen_table(parse_tables(gen_text))
    if header is None:
        print("找不到切段表（需要含「段号」「镜号」两列的表格）", file=sys.stderr)
        return 3

    c_seg = col_index(header, "段号")
    c_shot = col_index(header, "镜号")
    c_dur = col_index(header, "时长")
    c_mode = col_index(header, "模式")
    c_ref = col_index(header, "引用", "素材")
    c_first = col_index(header, "首帧")
    c_dep = col_index(header, "前置依赖", "关键事实")

    segments = []
    for r in rows:
        seg = get(r, c_seg)
        if not seg:
            continue
        segments.append(
            {
                "seg": seg,
                "shot": get(r, c_shot),
                "dur": to_float(get(r, c_dur)),
                "mode": get(r, c_mode),
                "ref": get(r, c_ref),
                "first": get(r, c_first),
                "dependency": get(r, c_dep),
            }
        )

    if not segments:
        print("切段表里没有数据行", file=sys.stderr)
        return 3

    info["segments"] = len(segments)

    # F1 每段都有镜号
    for s in segments:
        if not s["shot"]:
            fatal.append(f"[F1] {s['seg']} 缺镜号")

    # F2 时长闭合
    total = 0.0
    bad_dur = []
    for s in segments:
        if s["dur"] is None or s["dur"] <= 0:
            bad_dur.append(s["seg"])
        else:
            total += s["dur"]
    info["total_sec"] = round(total, 2)
    if bad_dur:
        fatal.append("[F2] 时长缺失或非正数：" + "、".join(bad_dur))
    if target is None:
        warn.append("[W5] 目标时长未解析，时长闭合检查已跳过（显式传 --target 恢复）")
    elif abs(total - target) > TOLERANCE_SEC:
        fatal.append(f"[F2] 时长不闭合：合计 {total:g}s，目标 {target:g}s，差 {abs(total - target):.1f}s（容差 1s）")

    # F3 引用不悬空
    defined = set()
    if asset_text:
        a_header, a_rows = find_asset_table(parse_tables(asset_text))
        if a_header is not None:
            c_id = col_index(a_header, "编号")
            for r in a_rows:
                aid = get(r, c_id).upper()
                if aid:
                    defined.add(aid)
    used = set()
    for s in segments:
        for aid in ASSET_ID.findall(s["ref"]):
            used.add(aid.upper())
    if defined:
        missing = sorted(used - defined)
        if missing:
            fatal.append("[F3] 引用未定义资产：" + "、".join(missing))
    elif used:
        warn.append("[W4] 未提供资产清单，跳过编号核对")

    # F4 主模式唯一
    main_modes = {s["mode"].strip() for s in segments if s["mode"].strip() and "文生" not in s["mode"]}
    if len(main_modes) > 1:
        fatal.append("[F4] 主模式混用：" + "、".join(sorted(main_modes)) + "（首尾帧与参考图必须二选一）")

    # W1 单段时长越界
    for s in segments:
        if s["dur"] is not None and (s["dur"] < MIN_SEG or s["dur"] > MAX_SEG):
            warn.append(f"[W1] {s['seg']} 时长 {s['dur']:g}s 超出 {MIN_SEG:g}–{MAX_SEG:g}s 建议区间")

    # W3 首尾帧模式却没写首帧
    for s in segments:
        if "首尾帧" in s["mode"] and not s["first"]:
            warn.append(f"[W3] {s['seg']} 声明首尾帧但首帧列为空")

    # F5-F7 检查逐段提示词结构
    blocks = {}
    matches = list(SEG_HEADING.finditer(gen_text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(gen_text)
        blocks[m.group(1).upper()] = gen_text[m.end():end]

    expected_segments = {s["seg"].upper() for s in segments}
    extra_blocks = sorted(set(blocks) - expected_segments)
    if extra_blocks:
        fatal.append("[F5] 多出逐段提示词小节：" + "、".join(extra_blocks))
    if not blocks:
        fatal.append("[F5] 未找到逐段提示词小节（### S01 形式）")
    else:
        missing_blocks = sorted(expected_segments - set(blocks))
        if missing_blocks:
            fatal.append("[F5] 缺逐段提示词小节：" + "、".join(missing_blocks))

        no_motion, no_sub = [], []
        for seg_id, body in blocks.items():
            if seg_id not in expected_segments:
                continue
            if not re.search(r"Motion\s*[:：]", body, re.I):
                no_motion.append(seg_id)
            if not re.search(r"No subtitles", body, re.I):
                no_sub.append(seg_id)
        if no_sub:
            fatal.append("[F6] 缺 `No subtitles`：" + "、".join(sorted(no_sub)))
        if no_motion:
            warn.append("[W2] 缺 `Motion:` 清单：" + "、".join(sorted(no_motion)))

        missing_fields = []
        for seg_id, body in blocks.items():
            if seg_id not in expected_segments:
                continue
            values = find_field_table(body)
            if values is None:
                missing_fields.append(f"{seg_id}缺画面字段表")
                continue
            absent = [field for field in TABLE_FIELDS if field not in values]
            blank = [
                field for field in TABLE_FIELDS
                if field in values and is_blank(values[field], field)
            ]
            details = []
            if absent:
                details.append("缺字段：" + "、".join(absent))
            if blank:
                details.append("值空：" + "、".join(blank))
            if details:
                missing_fields.append(f"{seg_id}" + "；".join(details))
        if missing_fields:
            fatal.append("[F7] 画面字段不完整：" + "；".join(sorted(missing_fields)))

    # F8 检查交接列：旧案例缺列会被标出；事实是否真的入镜由 G2 人工核对。
    if c_dep is None:
        fatal.append("[F8] 概览表缺前置依赖/关键事实列")
    else:
        unmapped = [s["seg"] for s in segments if is_blank(s["dependency"], "依赖/可见事实")]
        if unmapped:
            fatal.append("[F8] 概览表前置依赖/关键事实未填写：" + "、".join(unmapped))
        only_no = [s["seg"] for s in segments if s["dependency"].strip() == "无"]
        if only_no:
            fatal.append("[F8] 概览表只写了无，须补本段关键可见事实：" + "、".join(only_no))

    # ---- 输出 ----
    result = {
        "ok": not fatal,
        "info": info,
        "fatal": fatal,
        "warn": warn,
        "assets_defined": sorted(defined),
        "assets_used": sorted(used),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"生成清单：{gen_path}")
        print(f"段数 {len(segments)} ｜ 合计 {total:g}s" + (f" ｜ 目标 {target:g}s" if target else " ｜ 目标未提供"))
        print(f"资产：定义 {len(defined)} 个，引用 {len(used)} 个")
        print("-" * 52)
        if fatal:
            print(f"致命 {len(fatal)} 项：")
            for x in fatal:
                print("  ✗ " + x)
        if warn:
            print(f"告警 {len(warn)} 项：")
            for x in warn:
                print("  ! " + x)
        if not fatal:
            print("✓ 通过：可进入生成阶段" if warn else "✓ 全部通过")
        print("-" * 52)
        print("结论：" + ("通过（exit 0）" if not fatal else "不通过（exit 2）"))

    return 0 if not fatal else 2


if __name__ == "__main__":
    sys.exit(main())
