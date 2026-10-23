#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资产准备校验：清单与目录是否对得上、命名是否合规、尺寸是否够用。

用法：
    python check_assets.py --dir <制作目录>
    python check_assets.py --list 02-资产清单.md --img-dir 04-素材/01-资产图

退出码：0 通过 / 2 存在致命项 / 3 输入无法读取
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
# <编号>_<用途>_v<N>；用途允许出现下划线（如 丁克大脚丫_身份锚点）
NAME_RE = re.compile(r"^(?P<id>(?:PR|SC|CH|SP)-\d{2}[A-Z]?)_(?P<use>.+?)_v(?P<ver>\d+)$", re.I)
# 宽松取编号：文件名不合规时也能对上清单，避免误报「有标记却无文件」
ID_PREFIX = re.compile(r"^((?:PR|SC|CH|SP)-\d{2}[A-Z]?)", re.I)
ASSET_ID = re.compile(r"(?:PR|SC|CH|SP)-\d{2}[A-Z]?", re.I)
DONE_STATUS = ("已有", "已有备选", "完成", "已出")
MIN_SHORT_SIDE = 720


# ---------- markdown 表格 ----------
def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


def parse_tables(text: str):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = [split_row(b) for b in block]
            rows = [r for r in rows if r and not is_sep(r)]
            if len(rows) >= 2:
                out.append((rows[0], rows[1:]))
        else:
            i += 1
    return out


def col(header, *kws):
    for i, name in enumerate(header):
        for kw in kws:
            if kw in name:
                return i
    return None


def cell(row, idx):
    return row[idx].strip() if idx is not None and idx < len(row) else ""


# ---------- 图片尺寸（不依赖第三方库）----------
def image_size(path: Path):
    try:
        with path.open("rb") as f:
            head = f.read(32)
            if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
                w, h = struct.unpack(">II", head[16:24])
                return w, h
            if head.startswith(b"\xff\xd8"):
                f.seek(2)
                while True:
                    b = f.read(1)
                    if not b:
                        return None
                    if b != b"\xff":
                        continue
                    marker = f.read(1)
                    while marker == b"\xff":
                        marker = f.read(1)
                    if not marker:
                        return None
                    m = marker[0]
                    if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                        continue
                    ln_raw = f.read(2)
                    if len(ln_raw) < 2:
                        return None
                    seg_len = struct.unpack(">H", ln_raw)[0]
                    if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        data = f.read(5)
                        if len(data) < 5:
                            return None
                        h, w = struct.unpack(">HH", data[1:5])
                        return w, h
                    f.seek(seg_len - 2, 1)
    except OSError:
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="资产清单与图片目录一致性校验")
    ap.add_argument("--dir", help="制作目录")
    ap.add_argument("--list", help="资产清单路径")
    ap.add_argument("--img-dir", help="资产图目录")
    ap.add_argument("--sheet", help="生产工单路径（用于锚点候选数检查）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    base = Path(args.dir) if args.dir else None
    list_path = Path(args.list) if args.list else (base / "02-资产清单.md" if base else None)
    img_dir = Path(args.img_dir) if args.img_dir else (base / "04-素材" / "01-资产图" if base else None)
    sheet_path = Path(args.sheet) if args.sheet else (base / "04-素材" / "00-工单.md" if base else None)

    if not list_path or not list_path.exists():
        print(f"读不了资产清单：{list_path}", file=sys.stderr)
        return 3
    if not img_dir or not img_dir.is_dir():
        print(f"读不了资产图目录：{img_dir}", file=sys.stderr)
        return 3

    try:
        text = list_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"读不了资产清单：{exc}", file=sys.stderr)
        return 3

    header = rows = None
    for h, r in parse_tables(text):
        if col(h, "编号") is not None and col(h, "类型") is not None:
            header, rows = h, r
            break
    if header is None:
        print("资产清单里找不到含「编号」「类型」的表格", file=sys.stderr)
        return 3

    c_id, c_use = col(header, "编号"), col(header, "用途")
    c_status, c_level = col(header, "状态"), col(header, "级别")

    listed: dict[str, dict] = {}
    for r in rows:
        aid = cell(r, c_id).upper()
        if not aid:
            continue
        listed[aid] = {
            "use": cell(r, c_use),
            "status": cell(r, c_status) if c_status is not None else "",
            "level": cell(r, c_level) if c_level is not None else "",
        }

    files = [p for p in sorted(img_dir.iterdir()) if p.is_file() and p.suffix.lower() in IMG_EXT]

    fatal, warn, infos = [], [], []
    by_id: dict[str, list[Path]] = {}
    orphans, badnames = [], []

    for p in files:
        m = NAME_RE.match(p.stem)
        if m:
            aid = m.group("id").upper()
        else:
            badnames.append(p.name)
            m2 = ID_PREFIX.match(p.stem)
            if not m2:
                continue
            aid = m2.group(1).upper()
        by_id.setdefault(aid, []).append(p)

    # A2 命名
    if badnames:
        fatal.append("[A2] 文件名不合规（应为 <编号>_<用途>_v<N>）：" + "、".join(badnames[:8]))

    # A1 清单编号都有文件（状态为待补的除外）
    missing_required, missing_pending = [], []
    for aid, meta in listed.items():
        if by_id.get(aid):
            continue
        if meta["status"] and not any(k in meta["status"] for k in DONE_STATUS):
            missing_pending.append(aid)
        else:
            missing_required.append(aid)
    if missing_required:
        fatal.append("[A1] 清单标为已有但没有文件：" + "、".join(sorted(missing_required)))
    if missing_pending:
        infos.append("[A1] 待补资产（不计错）：" + "、".join(sorted(missing_pending)))

    # A3 孤儿文件
    for aid in sorted(by_id):
        if aid not in listed:
            orphans.append(aid)
    if orphans:
        warn.append("[A3] 目录里有清单外的资产：" + "、".join(orphans))

    # A4 分辨率
    small = []
    for p in files:
        size = image_size(p)
        if not size:
            continue
        w, h = size
        if min(w, h) < MIN_SHORT_SIDE:
            small.append(f"{p.name}({w}×{h})")
    if small:
        warn.append(f"[A4] 短边小于 {MIN_SHORT_SIDE}px：" + "、".join(small[:6]))

    # A5 锚点级候选数（需工单）
    sheet_rows = []
    if sheet_path and sheet_path.exists():
        try:
            st = sheet_path.read_text(encoding="utf-8")
            for h, r in parse_tables(st):
                if col(h, "编号") is not None and col(h, "级别") is not None:
                    sheet_rows = [(h, r)]
                    break
        except OSError:
            sheet_rows = []
    if sheet_rows:
        h, rws = sheet_rows[0]
        cid, clv = col(h, "编号"), col(h, "级别")
        ccd, cver = col(h, "候选"), col(h, "选定")
        thin = []
        for r in rws:
            aid = cell(r, cid).upper()
            if "锚点" not in cell(r, clv):
                continue
            raw = cell(r, ccd) if ccd is not None else ""
            m = re.search(r"\d+", raw)
            if m and int(m.group()) < 2:
                thin.append(f"{aid}(候选{m.group()})")
            if cver is not None and not cell(r, cver) and by_id.get(aid):
                thin.append(f"{aid}(未记选定版本)")
        if thin:
            warn.append("[A5] 锚点级候选不足或缺选定版本：" + "、".join(thin))

    # ---------- 输出 ----------
    result = {
        "ok": not fatal,
        "list": str(list_path),
        "img_dir": str(img_dir),
        "assets_listed": len(listed),
        "files": len(files),
        "fatal": fatal,
        "warn": warn,
        "info": infos,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if not fatal else 2

    print(f"资产清单：{list_path}")
    print(f"图片目录：{img_dir}")
    print(f"清单 {len(listed)} 个资产 ｜ 目录 {len(files)} 个文件")
    print("-" * 56)
    if infos:
        for x in infos:
            print("  · " + x)
    if fatal:
        print(f"致命 {len(fatal)} 项：")
        for x in fatal:
            print("  ✗ " + x)
    if warn:
        print(f"告警 {len(warn)} 项：")
        for x in warn:
            print("  ! " + x)
    if not fatal:
        print("✓ 通过：可进入视频生成" if warn else "✓ 全部通过")
    print("-" * 56)
    print("结论：" + ("通过（exit 0）" if not fatal else "不通过（exit 2）"))
    return 0 if not fatal else 2


if __name__ == "__main__":
    sys.exit(main())
