#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载后的片段体检（媒体层，不看画面好不好看）。

只回答五个客观问题：文件在不在、大小对不对、时长对不对、比例对不对、音轨在不在。
画面质量（变形、漂移、闪烁、文字重绘）和音频内容（有没有念错名字）必须靠人判定，脚本不判。

用法：
    python inspect_clip.py --file 04-素材/03-片段/S01_v1.mp4
    python inspect_clip.py --file S01_v1.mp4 --ratio 9:16 --duration 5
    python inspect_clip.py --file S01_v1.mp4 --expect-audio        # 要求有音轨
    python inspect_clip.py --file S01_v1.mp4 --no-expect-audio     # 要求无音轨
    python inspect_clip.py --dir 04-素材/03-片段

退出码：0 全部通过 / 2 有问题 / 3 环境缺失（找不到 ffprobe 或文件读不了）
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}

# 体积只做兜底提示：真正判「下到的是不是视频」靠有没有视频轨。
# 阈值不设高，纯色测试片压完只有几 KB，设高了会误报。
MIN_BYTES = 2_000


def ffprobe_bin() -> str:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    raise SystemExit("找不到 ffprobe，请先安装 ffmpeg 或把它加进 PATH。")


def probe(path: Path) -> dict:
    cmd = [
        ffprobe_bin(),
        "-v", "error",
        "-show_entries",
        "format=duration,size:stream=index,codec_type,width,height,codec_name,duration",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:300] or "ffprobe 读取失败")
    return json.loads(result.stdout or "{}")


def ratio_close(actual: float, expected: str, rel: float = 0.02) -> bool:
    parts = expected.split(":", 1)
    if len(parts) != 2:
        return False
    try:
        want = float(parts[0]) / float(parts[1])
    except (ValueError, ZeroDivisionError):
        return False
    return math.isclose(actual, want, rel_tol=rel, abs_tol=0.01)


def inspect(path: Path, ratio: str | None, expect_audio: bool | None,
            min_dur: float | None, max_dur: float | None) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        return {"file": str(path), "passed": False, "errors": ["文件不存在"]}

    size = path.stat().st_size
    if size == 0:
        errors.append("文件是空的")
    elif size < MIN_BYTES:
        warnings.append(f"文件只有 {size} 字节，多半不是正常片段")

    meta = probe(path)
    streams = meta.get("streams") or []
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if not video:
        errors.append("没有视频轨")

    duration = float((meta.get("format") or {}).get("duration") or 0)
    if duration <= 0:
        errors.append("读不到时长")
    else:
        if min_dur is not None and duration < min_dur - 0.3:
            errors.append(f"时长 {duration:.2f}s 短于预期 {min_dur:.2f}s")
        if max_dur is not None and duration > max_dur + 0.5:
            errors.append(f"时长 {duration:.2f}s 超过预期 {max_dur:.2f}s")

    # 三态：给了 --expect-audio 要求有，给了 --no-expect-audio 要求无，
    # 都不给就不判，只如实报告 hasAudio。
    # 人物对白与旁白由模型生成，所以「无声」是高危信号——不判对错，但要提示一句，
    # 免得空镜和有台词的段落都糊过去。
    if expect_audio is not None and expect_audio != bool(audio):
        errors.append("应该有音轨但没有" if expect_audio else "不该有音轨但有")
    elif expect_audio is None and not audio:
        warnings.append("没有音轨。这一段如果有台词，说明人物对白或旁白没生成出来")

    w = h = 0
    actual_ratio = None
    if video:
        w = int(video[0].get("width") or 0)
        h = int(video[0].get("height") or 0)
        if w and h:
            actual_ratio = round(w / h, 4)
            if ratio and not ratio_close(actual_ratio, ratio):
                errors.append(f"画面 {w}×{h} 不是 {ratio}")
            if h and w and h < 640 and w < 640:
                warnings.append(f"分辨率偏低（{w}×{h}），只适合试看")

    return {
        "file": str(path),
        "bytes": size,
        "duration": round(duration, 3),
        "size": f"{w}×{h}" if w and h else None,
        "aspectRatio": actual_ratio,
        "hasAudio": bool(audio),
        "codec": video[0].get("codec_name") if video else None,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="片段媒体体检")
    ap.add_argument("--file", help="单个视频文件")
    ap.add_argument("--dir", help="目录，批量体检其中的视频")
    ap.add_argument("--ratio", default=None, help="期望比例，如 9:16")
    ap.add_argument("--duration", type=float, default=None, help="期望时长（上下各留少量容差）")
    ap.add_argument("--min-duration", type=float, default=None)
    ap.add_argument("--max-duration", type=float, default=None)
    ap.add_argument(
        "--expect-audio",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="--expect-audio 要求有音轨，--no-expect-audio 要求无；都不给则不判",
    )
    args = ap.parse_args()

    if not args.file and not args.dir:
        raise SystemExit("给 --file 或 --dir。")

    min_dur, max_dur = args.min_duration, args.max_duration
    if args.duration is not None:
        min_dur = args.duration - 0.5 if min_dur is None else min_dur
        max_dur = args.duration + 0.5 if max_dur is None else max_dur

    if args.file:
        targets = [Path(args.file)]
    else:
        base = Path(args.dir)
        if not base.is_dir():
            print(json.dumps({"passed": False, "errors": [f"目录不存在：{base}"]}, ensure_ascii=False))
            return 3
        targets = sorted(p for p in base.iterdir() if p.suffix.lower() in VIDEO_EXT)
        if not targets:
            print(json.dumps({"passed": False, "errors": [f"{base} 里没有视频文件"]}, ensure_ascii=False))
            return 3

    results = []
    bad = 0
    for p in targets:
        try:
            r = inspect(p, args.ratio, args.expect_audio, min_dur, max_dur)
        except (RuntimeError, SystemExit) as exc:
            r = {"file": str(p), "passed": False, "errors": [str(exc)]}
        if not r["passed"]:
            bad += 1
        results.append(r)

    if args.file:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"total": len(results), "failed": bad, "items": results}, ensure_ascii=False, indent=2))
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
