#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report subtitle timing, dialogue gaps, and text density.

Subtitle gaps are a proxy for dialogue gaps, not a measurement of audio silence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]+\}")


def timestamp(value: str) -> float:
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid SRT timestamp: {value}")
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_srt(text: str) -> list[dict]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.splitlines()
        time_line = next((line for line in lines if "-->" in line), None)
        if time_line is None:
            continue
        start_text, end_text = time_line.split("-->", 1)
        start = timestamp(start_text)
        end = timestamp(end_text)
        if end <= start:
            raise ValueError(f"subtitle end must follow start: {time_line}")
        text_value = " ".join(line.strip() for line in lines[lines.index(time_line) + 1:])
        text_value = TAG_RE.sub("", text_value)
        chars = sum(
            unicodedata.category(char)[0] in {"L", "N"}
            for char in text_value
        )
        cues.append({"start": start, "end": end, "chars": chars, "text": text_value})
    if not cues:
        raise ValueError("no subtitle cues found")
    return sorted(cues, key=lambda cue: (cue["start"], cue["end"]))


def analyze(cues: list[dict], duration: float | None, window: float) -> dict:
    duration = duration if duration is not None else max(cue["end"] for cue in cues)
    if duration <= 0:
        raise ValueError("duration must be positive")
    if any(cue["start"] < 0 or cue["end"] > duration + 0.001 for cue in cues):
        raise ValueError("subtitle cue falls outside video duration")
    total_chars = sum(cue["chars"] for cue in cues)
    covered = []
    for cue in cues:
        start, end = max(0.0, cue["start"]), min(duration, cue["end"])
        if end <= start:
            continue
        if covered and start <= covered[-1][1]:
            covered[-1][1] = max(covered[-1][1], end)
        else:
            covered.append([start, end])

    gaps = []
    cursor = 0.0
    for start, end in covered:
        if start > cursor:
            gaps.append({"start": cursor, "end": start, "duration": start - cursor})
        cursor = max(cursor, end)
    if cursor < duration:
        gaps.append({"start": cursor, "end": duration, "duration": duration - cursor})

    windows = []
    position = 0.0
    while position < duration:
        end = min(position + window, duration)
        count = 0.0
        for cue in cues:
            overlap = max(0.0, min(end, cue["end"]) - max(position, cue["start"]))
            cue_duration = cue["end"] - cue["start"]
            if overlap and cue_duration:
                count += cue["chars"] * overlap / cue_duration
        windows.append({"start": position, "end": end, "chars": round(count)})
        position = end

    return {
        "duration": duration,
        "cue_count": len(cues),
        "char_count": total_chars,
        "density_chars_per_sec": total_chars / duration,
        "subtitle_covered_sec": sum(end - start for start, end in covered),
        "subtitle_coverage": sum(end - start for start, end in covered) / duration,
        "max_gap": max(gaps, key=lambda gap: gap["duration"], default=None),
        "gaps": sorted(gaps, key=lambda gap: gap["duration"], reverse=True),
        "windows": windows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report subtitle rhythm metrics")
    parser.add_argument("--srt", required=True, help="subtitle SRT file")
    parser.add_argument("--dur", type=float, help="full video duration in seconds")
    parser.add_argument("--max-gap", type=float, help="project-specific strict mode gap limit")
    parser.add_argument("--window", type=float, default=10.0, help="text density window size")
    parser.add_argument("--strict", action="store_true", help="exit 2 when maximum gap exceeds --max-gap")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args()

    try:
        text = Path(args.srt).read_text(encoding="utf-8-sig")
        if args.window <= 0:
            raise ValueError("window must be positive")
        if args.dur is not None and args.dur <= 0:
            raise ValueError("duration must be positive")
        if args.strict and (args.max_gap is None or args.max_gap < 0):
            raise ValueError("strict mode requires a non-negative --max-gap")
        result = analyze(parse_srt(text), args.dur, args.window)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    result["srt"] = args.srt
    result["max_gap_limit"] = args.max_gap if args.strict else None
    result["strict"] = args.strict
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"总时长 {result['duration']:.2f}s ｜ 句数 {result['cue_count']} ｜ "
            f"字数 {result['char_count']} ｜ 密度 {result['density_chars_per_sec']:.2f} 字/秒"
        )
        print(f"字幕覆盖 {result['subtitle_covered_sec']:.2f}s（{result['subtitle_coverage']:.1%}）；空档仅代理无台词，不代表音轨静音")
        gap = result["max_gap"]
        if gap:
            print(f"最大空档 {gap['duration']:.2f}s（{gap['start']:.2f} → {gap['end']:.2f}）")
        for item in result["gaps"][1:]:
            print(f"其余空档 {item['duration']:.2f}s（{item['start']:.2f} → {item['end']:.2f}）")
        print(f"{args.window:g}s 窗口字数：" + "  ".join(
            f"{item['start']:g}-{item['end']:g}:{item['chars']}" for item in result["windows"]
        ))
        if args.strict and gap and gap["duration"] > args.max_gap:
            print(f"超过严格阈值 {args.max_gap:g}s")
    return 2 if args.strict and result["max_gap"] and result["max_gap"]["duration"] > args.max_gap else 0


if __name__ == "__main__":
    sys.exit(main())
