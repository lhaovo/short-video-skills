#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a review-only contact sheet from selected asset versions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


ASSET_ID = re.compile(r"^(PR|SC|CH|SP)-\d{2}[A-Z]?$")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
CATEGORY_ORDER = {"PR": 0, "SC": 1, "CH": 2, "SP": 3}
CATEGORY_COLORS = {
    "PR": "#D97706",
    "SC": "#2563EB",
    "CH": "#DB2777",
    "SP": "#7C3AED",
}
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/System/Library/Fonts/NotoSansCJK.ttc"),
)
PENDING_MARKERS = ("待补", "待出", "待拍", "待叠字", "后期")


class SheetError(RuntimeError):
    pass


@dataclass
class Asset:
    asset_id: str
    category: str
    kind: str
    purpose: str
    source: str
    version: str
    path: Path
    sha256: str
    original_width: int
    original_height: int
    display_width: int
    display_height: int
    exif_orientation: int


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("*", "").replace("`", "")).strip()


def markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    tables: list[tuple[list[str], list[list[str]]]] = []
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
        rows = [[normalized(cell) for cell in line.strip().strip("|").split("|")] for line in block]
        rows = [row for row in rows if not all(cell and set(cell) <= {"-", ":"} for cell in row)]
        if len(rows) >= 2:
            tables.append((rows[0], rows[1:]))
    return tables


def find_column(header: list[str], *keywords: str) -> int | None:
    for index, name in enumerate(header):
        if any(keyword in name for keyword in keywords):
            return index
    return None


def cell(row: list[str], index: int | None) -> str:
    return row[index] if index is not None and index < len(row) else ""


def parse_version(value: str) -> str:
    match = re.search(r"(?<![A-Za-z])v(\d+)\b", value, re.I)
    return f"v{match.group(1)}" if match else ""


def read_selected_assets(project: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    asset_list = project / "02-资产清单.md"
    work_order = project / "04-素材" / "00-工单.md"
    if not asset_list.is_file():
        raise SheetError(f"缺少资产清单：{asset_list}")

    text = asset_list.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s*资产清单\s*·\s*(.+)$", text, re.M)
    title = title_match.group(1).strip() if title_match else project.name

    selected: list[dict[str, str]] = []
    warnings: list[str] = []
    list_header = None
    list_rows = []
    for header, rows in markdown_tables(text):
        if (
            find_column(header, "编号") is not None
            and find_column(header, "类型") is not None
            and find_column(header, "状态") is not None
        ):
            list_header, list_rows = header, rows
            break
    if list_header is None:
        raise SheetError("资产清单中找不到含「编号 / 类型 / 状态」的总表")

    order_versions: dict[str, str] = {}
    if work_order.is_file():
        for header, rows in markdown_tables(work_order.read_text(encoding="utf-8")):
            id_col = find_column(header, "编号")
            version_col = find_column(header, "采用版本", "选定版本", "定版")
            if id_col is None or version_col is None:
                continue
            for row in rows:
                asset_id = cell(row, id_col).upper()
                version = parse_version(cell(row, version_col))
                if ASSET_ID.match(asset_id) and version:
                    order_versions[asset_id] = version
            break

    id_col = find_column(list_header, "编号")
    kind_col = find_column(list_header, "类型")
    purpose_col = find_column(list_header, "用途")
    source_col = find_column(list_header, "来源")
    status_col = find_column(list_header, "状态")
    seen: set[str] = set()
    for row in list_rows:
        asset_id = cell(row, id_col).upper()
        if not ASSET_ID.match(asset_id):
            continue
        if asset_id in seen:
            raise SheetError(f"资产清单中编号重复：{asset_id}")
        seen.add(asset_id)
        status = cell(row, status_col)
        if any(marker in status for marker in PENDING_MARKERS):
            continue
        status_version = parse_version(status)
        order_version = order_versions.get(asset_id, "")
        if status_version and order_version and status_version != order_version:
            raise SheetError(
                f"{asset_id} 的定版冲突：清单状态为 {status_version}，工单为 {order_version}"
            )
        version = order_version or status_version
        selected.append(
            {
                "asset_id": asset_id,
                "category": asset_id.split("-", 1)[0],
                "kind": cell(row, kind_col),
                "purpose": cell(row, purpose_col),
                "source": cell(row, source_col),
                "status": status,
                "version": version,
            }
        )
        if not version:
            warnings.append(f"{asset_id} 未在清单/工单中写明定版版本")
    return title, selected, warnings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_asset_file(asset_dir: Path, item: dict[str, str], warnings: list[str]) -> Path:
    asset_id = item["asset_id"]
    version = item["version"]
    pattern = re.compile(
        rf"^{re.escape(asset_id)}_.+_{re.escape(version)}\.(?:png|jpe?g|webp)$",
        re.I,
    )
    files = sorted(path for path in asset_dir.iterdir() if path.is_file() and pattern.match(path.name))
    if version:
        if len(files) == 1:
            return files[0]
        if not files:
            raise SheetError(f"{asset_id} 找不到定版文件 {version}")
        raise SheetError(f"{asset_id} 的 {version} 对应多个文件：" + "、".join(p.name for p in files))

    all_files = sorted(
        path
        for path in asset_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in IMAGE_EXTENSIONS
        and re.match(rf"^{re.escape(asset_id)}_", path.name, re.I)
    )
    if len(all_files) == 1:
        warnings.append(f"{asset_id} 未写定版版本，按唯一文件 {all_files[0].name} 生成审阅图")
        return all_files[0]
    if not all_files:
        raise SheetError(f"{asset_id} 在资产目录中没有图片")
    raise SheetError(f"{asset_id} 有多个版本但未记录定版：" + "、".join(p.name for p in all_files))


def load_asset(asset_dir: Path, item: dict[str, str], warnings: list[str]) -> Asset:
    path = find_asset_file(asset_dir, item, warnings)
    before_hash = sha256_file(path)
    try:
        with Image.open(path) as opened:
            orientation = int((opened.getexif() or {}).get(274, 1))
            original_size = opened.size
            transposed = ImageOps.exif_transpose(opened)
            display_size = transposed.size
    except (OSError, UnidentifiedImageError) as exc:
        raise SheetError(f"无法读取资产图 {path}：{exc}") from exc
    return Asset(
        asset_id=item["asset_id"],
        category=item["category"],
        kind=item["kind"],
        purpose=item["purpose"],
        source=item["source"],
        version=item["version"] or parse_version(path.stem),
        path=path,
        sha256=before_hash,
        original_width=original_size[0],
        original_height=original_size[1],
        display_width=display_size[0],
        display_height=display_size[1],
        exif_orientation=orientation,
    )


def find_font(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else []
    env_font = os.environ.get("ASSET_REVIEW_FONT")
    if env_font:
        candidates.append(Path(env_font))
    candidates.extend(FONT_CANDIDATES)
    for path in candidates:
        if path.is_file():
            return path
    raise SheetError("找不到 Noto Sans CJK SC；请用 --font 指定字体文件")


def format_asset(asset: Asset) -> Image.Image:
    with Image.open(asset.path) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, rgba).convert("RGB")
        else:
            image = image.convert("RGB")
        return image.copy()


def image_for_asset(asset: Asset) -> Image.Image:
    return format_asset(asset)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = char
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if lines and "".join(lines) != text:
        last = lines[-1]
        while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def draw_label_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    asset: Asset,
    font_body: ImageFont.FreeTypeFont,
    font_small: ImageFont.FreeTypeFont,
) -> int:
    black = "#18221D"
    muted = "#5C695F"
    line_height = int(font_body.size * 1.25)
    cursor = y
    draw.text((x, cursor), f"{asset.asset_id}  {asset.kind}", font=font_body, fill=black)
    cursor += line_height
    for line in wrap_text(draw, asset.purpose, font_small, width, 2):
        draw.text((x, cursor), line, font=font_small, fill=muted)
        cursor += int(font_small.size * 1.2)
    draw.text((x, cursor), f"定版 {asset.version}  ·  {asset.source}", font=font_small, fill=muted)
    cursor += int(font_small.size * 1.2)
    for line in wrap_text(draw, asset.path.name, font_small, width, 2):
        draw.text((x, cursor), line, font=font_small, fill="#7A857C")
        cursor += int(font_small.size * 1.2)
    return cursor


def render_sheet(
    title: str,
    assets: list[Asset],
    out: Path,
    font_path: Path,
    columns: int,
    canvas_size: tuple[int, int] | None,
    quality: int,
) -> tuple[int, int]:
    rows = (len(assets) + columns - 1) // columns
    margin = 32
    gap = 14
    header_height = 112
    footer_height = 40
    if canvas_size:
        width, height = canvas_size
    else:
        width = max(1580, margin * 2 + columns * 360 + (columns - 1) * gap)
        card_height = 620
        height = header_height + footer_height + margin * 2 + rows * card_height + (rows - 1) * gap
    available_width = width - margin * 2 - gap * (columns - 1)
    card_width = available_width // columns
    available_height = height - header_height - footer_height - margin * 2 - gap * (rows - 1)
    card_height = available_height // rows
    if card_width < 120 or card_height < 300:
        raise SheetError("画布或列数过小，卡片无法容纳图片与文字")

    canvas = Image.new("RGB", (width, height), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    title_font = ImageFont.truetype(str(font_path), 34)
    subtitle_font = ImageFont.truetype(str(font_path), 18)
    body_font = ImageFont.truetype(str(font_path), 19)
    small_font = ImageFont.truetype(str(font_path), 15)

    draw.text((margin, 26), "定版资产审阅总览", font=title_font, fill="#111814")
    draw.text(
        (margin, 72),
        f"{title}  ·  {len(assets)} 项  ·  按 PR / SC / CH / SP 排序",
        font=subtitle_font,
        fill="#657066",
    )

    content_top = header_height
    for index, asset in enumerate(assets):
        row, column = divmod(index, columns)
        x = margin + column * (card_width + gap)
        y = content_top + row * (card_height + gap)
        color = CATEGORY_COLORS[asset.category]
        draw.rounded_rectangle(
            (x, y, x + card_width, y + card_height),
            radius=12,
            fill="#FFFFFF",
            outline="#D9E0DB",
            width=2,
        )
        draw.rounded_rectangle(
            (x, y, x + card_width, y + 10),
            radius=5,
            fill=color,
        )
        label_y = y + 22
        label_bottom = draw_label_block(
            draw,
            x + 14,
            label_y,
            card_width - 28,
            asset,
            body_font,
            small_font,
        )
        image_top = label_bottom + 8
        image_bottom = y + card_height - 12
        viewport = (
            x + 14,
            image_top,
            x + card_width - 14,
            image_bottom,
        )
        viewport_w = viewport[2] - viewport[0]
        viewport_h = viewport[3] - viewport[1]
        if viewport_w <= 0 or viewport_h <= 0:
            raise SheetError(f"{asset.asset_id} 的卡片没有足够图片区域")
        draw.rectangle(viewport, fill="#FFFFFF")
        image = image_for_asset(asset)
        image.thumbnail((viewport_w, viewport_h), Image.Resampling.LANCZOS)
        image_x = viewport[0] + (viewport_w - image.width) // 2
        image_y = viewport[1] + (viewport_h - image.height) // 2
        canvas.paste(image, (image_x, image_y))

    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return canvas.size


def next_output(project: Path) -> Path:
    output_dir = project / "04-素材" / "00-审阅"
    for index in range(1, 1000):
        candidate = output_dir / f"定版资产总览-v{index}.jpg"
        if not candidate.exists():
            return candidate
    raise SheetError("无法分配新的审阅图版本号")


def write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build(args: argparse.Namespace) -> dict:
    project = Path(args.project).expanduser().resolve()
    asset_dir = project / "04-素材" / "01-资产图"
    if not asset_dir.is_dir():
        raise SheetError(f"缺少资产图目录：{asset_dir}")
    out = Path(args.output).expanduser().resolve() if args.output else next_output(project)
    if out.suffix.lower() not in {".jpg", ".jpeg"}:
        raise SheetError("审阅总览只输出 JPEG，请使用 .jpg 或 .jpeg")
    if out.exists() and not args.overwrite:
        raise SheetError(f"输出已存在，拒绝覆盖：{out}")
    if asset_dir == out.parent or asset_dir in out.parents:
        raise SheetError("审阅总览不能写进 01-资产图；请放到 04-素材/00-审阅")

    title, selected, warnings = read_selected_assets(project)
    if args.expected_count is not None and len(selected) != args.expected_count:
        raise SheetError(
            f"定版资产数量不符合预期：期望 {args.expected_count}，实际 {len(selected)}；"
            f"编号：{', '.join(item['asset_id'] for item in selected)}"
        )
    if not selected:
        raise SheetError("没有可审阅的定版资产")

    deduped: dict[str, dict[str, str]] = {}
    for item in selected:
        if item["asset_id"] in deduped:
            raise SheetError(f"资产编号重复：{item['asset_id']}")
        deduped[item["asset_id"]] = item
    selected = sorted(
        deduped.values(),
        key=lambda item: (
            CATEGORY_ORDER[item["category"]],
            int(re.search(r"\d{2}", item["asset_id"]).group()),
            item["asset_id"],
        ),
    )

    assets = [load_asset(asset_dir, item, warnings) for item in selected]
    font_path = find_font(args.font)
    canvas_size = args.canvas
    width, height = render_sheet(
        title,
        assets,
        out,
        font_path,
        args.columns,
        canvas_size,
        args.quality,
    )

    changed = [
        asset.asset_id for asset in assets if sha256_file(asset.path) != asset.sha256
    ]
    if changed:
        raise SheetError("源资产在拼图期间发生变化：" + "、".join(changed))

    metadata_path = out.with_suffix(".json")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canvas": {"width": width, "height": height},
        "columns": args.columns,
        "rows": (len(assets) + args.columns - 1) // args.columns,
        "expected_count": args.expected_count,
        "count": len(assets),
        "title": title,
        "warnings": warnings,
        "assets": [
            {
                "asset_id": asset.asset_id,
                "type": asset.kind,
                "purpose": asset.purpose,
                "source": asset.source,
                "version": asset.version,
                "file": str(asset.path),
                "filename": asset.path.name,
                "sha256": asset.sha256,
                "original_size": [asset.original_width, asset.original_height],
                "display_size": [asset.display_width, asset.display_height],
                "exif_orientation": asset.exif_orientation,
            }
            for asset in assets
        ],
    }
    write_json(metadata_path, payload)
    return {"sheet": str(out), "metadata": str(metadata_path), **payload}


def parse_canvas(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)x(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError("--canvas 必须是 WIDTHxHEIGHT，例如 1580x2756")
    width, height = int(match.group(1)), int(match.group(2))
    if width < 320 or height < 320:
        raise argparse.ArgumentTypeError("画布至少为 320x320")
    return width, height


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="生成定版资产审阅接触印样")
    parser.add_argument("--project", required=True, help="制作目录")
    parser.add_argument("--expected-count", type=positive_int, help="可选的完整性校验数量")
    parser.add_argument("--columns", type=int, default=4, choices=range(1, 10))
    parser.add_argument("--canvas", type=parse_canvas, help="可选固定画布，例如 1580x2756")
    parser.add_argument("--quality", type=int, default=92, choices=range(60, 101))
    parser.add_argument("--output", help="输出 JPEG；默认写入 04-素材/00-审阅并自动递增版本")
    parser.add_argument("--overwrite", action="store_true", help="仅显式允许时覆盖指定输出")
    parser.add_argument("--font", help="Noto Sans CJK SC 字体路径")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = build(args)
    except (SheetError, OSError) as exc:
        print(f"接触印样生成失败：{exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"审阅图：{result['sheet']}")
        print(f"旁车记录：{result['metadata']}")
        print(f"资产数：{result['count']} ｜ 画布：{result['canvas']['width']}×{result['canvas']['height']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
