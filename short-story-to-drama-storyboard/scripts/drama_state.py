#!/usr/bin/env python3
"""File-backed state manager for short-story-to-drama-storyboard."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE = "state.json"
SOURCE_SNAPSHOT = "source.story.md"
MIN_SOURCE_CHARS = 1_000
MAX_SOURCE_CHARS = 60_000
MAX_EPISODES = 40


class SkillError(Exception):
    """A user-correctable workflow error."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SkillError(f"File not found: {path}") from exc


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SkillError(f"Expected a JSON object in {path}")
    return value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def visible_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def require_text(value: Any, field: str, minimum: int = 1) -> str:
    if not isinstance(value, str):
        raise SkillError(f"{field} must be a string")
    cleaned = value.strip()
    if len(cleaned) < minimum:
        raise SkillError(f"{field} must contain at least {minimum} characters")
    return cleaned


def optional_text_list(value: Any, field: str, maximum: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise SkillError(f"{field} must be a list with at most {maximum} items")
    return [require_text(item, f"{field}[{index}]", minimum=2) for index, item in enumerate(value)]


def require_text_list(value: Any, field: str, minimum: int, maximum: int) -> list[str]:
    items = optional_text_list(value, field, maximum)
    if len(items) < minimum:
        raise SkillError(f"{field} must contain at least {minimum} items")
    return items


def require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SkillError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise SkillError(f"{field} must be between {minimum} and {maximum}")
    return value


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    atomic_write(root / STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def load_state(root: Path) -> dict[str, Any]:
    state = read_json(root / STATE_FILE)
    if state.get("schema_version") != 1:
        raise SkillError("Unsupported state schema; expected schema_version 1")
    return state


def source_title(content: str, fallback: str) -> str:
    match = re.search(r"^\s*#\s+(.+?)\s*$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def find_item(items: list[dict[str, Any]], order: int) -> dict[str, Any] | None:
    return next((item for item in items if item["order"] == order), None)


def source_status(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    source = state["source"]
    source_path = Path(source["path"])
    snapshot_path = root / SOURCE_SNAPSHOT
    snapshot_content = read_text(snapshot_path)
    snapshot_valid = sha256_text(snapshot_content) == source["snapshot_sha256"]
    if not source_path.exists():
        return {
            "snapshot_valid": snapshot_valid,
            "source_available": False,
            "source_changed": False,
            "reason": "original source path is unavailable; the immutable snapshot remains usable",
        }
    current = sha256_text(read_text(source_path))
    changed = current != source["source_sha256"]
    return {
        "snapshot_valid": snapshot_valid,
        "source_available": True,
        "source_changed": changed,
        "reason": "source has changed since initialization" if changed else "source matches the accepted snapshot",
    }


def ensure_source_usable(root: Path, state: dict[str, Any]) -> None:
    status = source_status(root, state)
    if not status["snapshot_valid"]:
        raise SkillError("source.story.md has been modified; restore it or create a new drama project")
    if status["source_changed"]:
        raise SkillError(
            "The original short story changed after initialization; create a new drama version or explicitly replan"
        )


def adaptation_contract(raw: Any, episode_count: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("adaptation input must be a JSON object")
    raw_characters = raw.get("characters")
    if not isinstance(raw_characters, list) or not 1 <= len(raw_characters) <= 30:
        raise SkillError("adaptation.characters must contain 1-30 items")
    characters: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, item in enumerate(raw_characters):
        if not isinstance(item, dict):
            raise SkillError(f"adaptation.characters[{index}] must be an object")
        name = require_text(item.get("name"), f"characters[{index}].name")
        if name in names:
            raise SkillError(f"Duplicate character name: {name}")
        names.add(name)
        characters.append(
            {
                "name": name,
                "role": require_text(item.get("role"), f"characters[{index}].role", minimum=2),
                "motivation": require_text(
                    item.get("motivation"), f"characters[{index}].motivation", minimum=4
                ),
                "visual_anchor": require_text(
                    item.get("visual_anchor"),
                    f"characters[{index}].visual_anchor",
                    minimum=8,
                ),
            }
        )
    paywall_raw = raw.get("paywall_plan")
    paywall_plan = None
    if paywall_raw is not None:
        if not isinstance(paywall_raw, dict):
            raise SkillError("adaptation.paywall_plan must be an object or null")
        first = require_int(
            paywall_raw.get("first_paywall_at"),
            "paywall_plan.first_paywall_at",
            1,
            episode_count,
        )
        free = require_int(
            paywall_raw.get("free_episodes"),
            "paywall_plan.free_episodes",
            0,
            episode_count,
        )
        if free >= first:
            raise SkillError("paywall_plan.free_episodes must be lower than first_paywall_at")
        paywall_plan = {
            "first_paywall_at": first,
            "free_episodes": free,
            "cadence": require_int(
                paywall_raw.get("cadence"), "paywall_plan.cadence", 1, 10
            ),
            "cliffhanger_threshold": require_int(
                paywall_raw.get("cliffhanger_threshold"),
                "paywall_plan.cliffhanger_threshold",
                0,
                100,
            ),
            "note": require_text(paywall_raw.get("note"), "paywall_plan.note", minimum=4),
        }
    return {
        "title": require_text(raw.get("title"), "adaptation.title"),
        "genre": require_text(raw.get("genre"), "adaptation.genre", minimum=2),
        "target_audience": require_text(
            raw.get("target_audience"), "adaptation.target_audience", minimum=4
        ),
        "logline": require_text(raw.get("logline"), "adaptation.logline", minimum=8),
        "positioning": require_text(
            raw.get("positioning"), "adaptation.positioning", minimum=4
        ),
        "main_pleasure_line": require_text(
            raw.get("main_pleasure_line"), "adaptation.main_pleasure_line", minimum=4
        ),
        "adaptation_strategy": require_text(
            raw.get("adaptation_strategy"), "adaptation.adaptation_strategy", minimum=8
        ),
        "must_keep": require_text_list(
            raw.get("must_keep"), "adaptation.must_keep", minimum=3, maximum=20
        ),
        "allowed_changes": optional_text_list(
            raw.get("allowed_changes"), "adaptation.allowed_changes", maximum=20
        ),
        "deviations": optional_text_list(
            raw.get("deviations"), "adaptation.deviations", maximum=20
        ),
        "characters": characters,
        "paywall_plan": paywall_plan,
    }


def episodes_contract(raw: Any, episode_count: int, default_duration: int) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        raise SkillError("episodes input must be a JSON object")
    raw_episodes = raw.get("episodes")
    if not isinstance(raw_episodes, list) or len(raw_episodes) != episode_count:
        raise SkillError(f"episodes must contain exactly {episode_count} items")
    episodes: list[dict[str, Any]] = []
    for index, item in enumerate(raw_episodes):
        if not isinstance(item, dict):
            raise SkillError(f"episodes[{index}] must be an object")
        order = require_int(item.get("order"), f"episodes[{index}].order", 1, MAX_EPISODES)
        if order != index + 1:
            raise SkillError("Episode orders must be consecutive starting at 1")
        target_duration = item.get("target_duration_sec", default_duration)
        episodes.append(
            {
                "order": order,
                "title": require_text(item.get("title"), f"episodes[{index}].title"),
                "hook_opening": require_text(
                    item.get("hook_opening"), f"episodes[{index}].hook_opening", minimum=4
                ),
                "hook_type": require_text(
                    item.get("hook_type"), f"episodes[{index}].hook_type", minimum=2
                ),
                "conflict": require_text(
                    item.get("conflict"), f"episodes[{index}].conflict", minimum=4
                ),
                "cliffhanger": require_text(
                    item.get("cliffhanger"), f"episodes[{index}].cliffhanger", minimum=4
                ),
                "emotion_net": require_int(
                    item.get("emotion_net"), f"episodes[{index}].emotion_net", -5, 5
                ),
                "source_beats": require_text_list(
                    item.get("source_beats"),
                    f"episodes[{index}].source_beats",
                    minimum=1,
                    maximum=12,
                ),
                "target_duration_sec": require_int(
                    target_duration,
                    f"episodes[{index}].target_duration_sec",
                    20,
                    300,
                ),
                "is_paywall": bool(item.get("is_paywall", False)),
            }
        )
    return episodes


def script_contract(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("script input must be a JSON object")
    return {
        "content": require_text(raw.get("content"), "script.content", minimum=100),
        "duration_sec": require_int(raw.get("duration_sec"), "script.duration_sec", 20, 300),
        "scene_count": require_int(raw.get("scene_count"), "script.scene_count", 1, 12),
        "opening_3s": require_text(raw.get("opening_3s"), "script.opening_3s", minimum=4),
        "ending_cliffhanger": require_text(
            raw.get("ending_cliffhanger"), "script.ending_cliffhanger", minimum=4
        ),
        "newly_introduced_facts": optional_text_list(
            raw.get("newly_introduced_facts"), "script.newly_introduced_facts", maximum=20
        ),
        "episode_summary": require_text(
            raw.get("episode_summary"), "script.episode_summary", minimum=4
        ),
    }


def quality_contract(
    raw: Any,
    episode: dict[str, Any],
    paywall_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("quality input must be a JSON object")
    status = raw.get("status")
    if status not in {"approved", "continue_with_warning", "repairable", "blocked"}:
        raise SkillError(
            "quality.status must be approved, continue_with_warning, repairable, or blocked"
        )
    raw_score = raw.get("score")
    if not isinstance(raw_score, dict):
        raise SkillError("quality.score must be an object")
    score = {
        key: require_int(raw_score.get(key), f"quality.score.{key}", 0, 100)
        for key in ("hook", "density", "paywall", "emotion", "duration", "consistency", "overall")
    }
    raw_flags = raw.get("flags", [])
    if not isinstance(raw_flags, list) or len(raw_flags) > 30:
        raise SkillError("quality.flags must be a list with at most 30 items")
    flags: list[dict[str, str]] = []
    for index, item in enumerate(raw_flags):
        if not isinstance(item, dict):
            raise SkillError(f"quality.flags[{index}] must be an object")
        severity = item.get("severity")
        if severity not in {"low", "medium", "high", "critical"}:
            raise SkillError(f"quality.flags[{index}].severity is invalid")
        flags.append(
            {
                "severity": severity,
                "code": require_text(item.get("code"), f"quality.flags[{index}].code"),
                "evidence": require_text(
                    item.get("evidence"), f"quality.flags[{index}].evidence", minimum=4
                ),
                "suggestion": require_text(
                    item.get("suggestion"),
                    f"quality.flags[{index}].suggestion",
                    minimum=4,
                ),
            }
        )

    if any(flag["severity"] == "critical" for flag in flags):
        status = "blocked"
    elif any(flag["severity"] == "high" for flag in flags) and status != "blocked":
        status = "repairable"
    elif any(flag["severity"] == "medium" for flag in flags) and status == "approved":
        status = "continue_with_warning"

    if (
        paywall_plan
        and episode["order"] == paywall_plan["first_paywall_at"]
        and score["paywall"] < paywall_plan["cliffhanger_threshold"]
        and status in {"approved", "continue_with_warning"}
    ):
        status = "repairable"
        flags.append(
            {
                "severity": "high",
                "code": "paywall_below_threshold",
                "evidence": f"付费卡点评分 {score['paywall']} 低于计划阈值 {paywall_plan['cliffhanger_threshold']}。",
                "suggestion": "强化首付费集的结尾反打、身份揭示或不可逆危机。",
            }
        )

    repair_plan = raw.get("repair_plan")
    normalized_repair = None
    if repair_plan is not None:
        if not isinstance(repair_plan, dict):
            raise SkillError("quality.repair_plan must be an object or null")
        normalized_repair = {
            "mode": repair_plan.get("mode"),
            "instruction": require_text(
                repair_plan.get("instruction"), "quality.repair_plan.instruction", minimum=4
            ),
        }
        if normalized_repair["mode"] not in {"patch", "regenerate"}:
            raise SkillError("quality.repair_plan.mode must be patch or regenerate")
    if status in {"repairable", "blocked"} and normalized_repair is None:
        suggestions = [flag["suggestion"] for flag in flags]
        normalized_repair = {
            "mode": "patch",
            "instruction": "；".join(suggestions) or "根据质量问题重写本集。",
        }
    return {"status": status, "score": score, "flags": flags, "repair_plan": normalized_repair}


def storyboard_contract(raw: Any, character_names: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("storyboard input must be a JSON object")
    raw_shots = raw.get("shots")
    if not isinstance(raw_shots, list) or not 1 <= len(raw_shots) <= 40:
        raise SkillError("storyboard.shots must contain 1-40 items")
    shots: list[dict[str, Any]] = []
    for index, item in enumerate(raw_shots):
        if not isinstance(item, dict):
            raise SkillError(f"storyboard.shots[{index}] must be an object")
        order = require_int(
            item.get("order"), f"storyboard.shots[{index}].order", 1, 40
        )
        if order != index + 1:
            raise SkillError("Storyboard shot orders must be consecutive starting at 1")
        refs = optional_text_list(
            item.get("character_refs"), f"storyboard.shots[{index}].character_refs", 20
        )
        unknown = sorted(set(refs) - character_names)
        if unknown:
            raise SkillError(f"Storyboard references unknown characters: {unknown}")
        shots.append(
            {
                "order": order,
                "shot_size": require_text(
                    item.get("shot_size"), f"storyboard.shots[{index}].shot_size"
                ),
                "camera_move": require_text(
                    item.get("camera_move"), f"storyboard.shots[{index}].camera_move"
                ),
                "duration_sec": require_int(
                    item.get("duration_sec"),
                    f"storyboard.shots[{index}].duration_sec",
                    1,
                    30,
                ),
                "location": require_text(
                    item.get("location"), f"storyboard.shots[{index}].location", minimum=2
                ),
                "action": require_text(
                    item.get("action"), f"storyboard.shots[{index}].action", minimum=4
                ),
                "dialogue": (
                    require_text(
                        item.get("dialogue"), f"storyboard.shots[{index}].dialogue"
                    )
                    if item.get("dialogue")
                    else ""
                ),
                "character_refs": refs,
                "visual_prompt": require_text(
                    item.get("visual_prompt"),
                    f"storyboard.shots[{index}].visual_prompt",
                    minimum=8,
                ),
            }
        )
    return {
        "summary": require_text(raw.get("summary"), "storyboard.summary", minimum=4),
        "shots": shots,
    }


def render_adaptation(root: Path, state: dict[str, Any]) -> None:
    adaptation = state.get("adaptation")
    if not adaptation:
        return
    lines = [
        f"# 短剧改编：{adaptation['title']}",
        "",
        f"- 题材：{adaptation['genre']}",
        f"- 目标观众：{adaptation['target_audience']}",
        f"- 一句话梗概：{adaptation['logline']}",
        f"- 短剧定位：{adaptation['positioning']}",
        f"- 主爽点/情绪线：{adaptation['main_pleasure_line']}",
        f"- 改编策略：{adaptation['adaptation_strategy']}",
        "",
        "## 必须保留",
        "",
    ]
    lines.extend(f"- {item}" for item in adaptation["must_keep"])
    lines.extend(["", "## 允许压缩或合并", ""])
    if adaptation["allowed_changes"]:
        lines.extend(f"- {item}" for item in adaptation["allowed_changes"])
    else:
        lines.append("- 无")
    lines.extend(["", "## 新增或改写的明确偏离", ""])
    if adaptation["deviations"]:
        lines.extend(f"- {item}" for item in adaptation["deviations"])
    else:
        lines.append("- 无")
    lines.extend(["", "## 角色视觉锚点", ""])
    for character in adaptation["characters"]:
        lines.extend(
            [
                f"### {character['name']}",
                "",
                f"- 功能：{character['role']}",
                f"- 动机：{character['motivation']}",
                f"- 视觉锚点：{character['visual_anchor']}",
                "",
            ]
        )
    if adaptation["paywall_plan"]:
        plan = adaptation["paywall_plan"]
        lines.extend(
            [
                "## 付费卡点",
                "",
                f"- 免费集数：{plan['free_episodes']}",
                f"- 首次付费：第 {plan['first_paywall_at']} 集",
                f"- 后续节奏：每 {plan['cadence']} 集",
                f"- 卡点阈值：{plan['cliffhanger_threshold']}",
                f"- 说明：{plan['note']}",
                "",
            ]
        )
    atomic_write(root / "adaptation.md", "\n".join(lines))


def render_episodes(root: Path, state: dict[str, Any]) -> None:
    episodes = state.get("episodes", [])
    if not episodes:
        return
    atomic_write(
        root / "episodes.json",
        json.dumps({"episodes": episodes}, ensure_ascii=False, indent=2) + "\n",
    )
    lines = ["# 分集大纲", ""]
    for episode in episodes:
        paywall = "｜付费卡点" if episode["is_paywall"] else ""
        lines.extend(
            [
                f"## 第 {episode['order']} 集《{episode['title']}》{paywall}",
                "",
                f"- 黄金3秒：{episode['hook_opening']}",
                f"- 钩子类型：{episode['hook_type']}",
                f"- 核心冲突：{episode['conflict']}",
                f"- 集尾卡点：{episode['cliffhanger']}",
                f"- 情绪净值：{episode['emotion_net']}",
                f"- 目标时长：{episode['target_duration_sec']} 秒",
                f"- 来源节拍：{'、'.join(episode['source_beats'])}",
                "",
            ]
        )
    atomic_write(root / "episodes.md", "\n".join(lines))


def render_script_file(root: Path, state: dict[str, Any], episode_order: int) -> None:
    script = find_item(state["scripts"], episode_order)
    episode = find_item(state["episodes"], episode_order)
    if not script or not episode:
        return
    content = (
        f"# 第 {episode_order} 集《{episode['title']}》\n\n"
        f"{script['content'].strip()}\n"
    )
    atomic_write(root / "scripts" / f"{episode_order:02d}.md", content)
    atomic_write(
        root / "scripts" / f"{episode_order:02d}.json",
        json.dumps(script, ensure_ascii=False, indent=2) + "\n",
    )


def render_quality_file(root: Path, state: dict[str, Any], episode_order: int) -> None:
    quality = find_item(state["qualities"], episode_order)
    if quality:
        atomic_write(
            root / "quality" / f"{episode_order:02d}.json",
            json.dumps(quality, ensure_ascii=False, indent=2) + "\n",
        )


def storyboard_markdown(episode: dict[str, Any], storyboard: dict[str, Any]) -> str:
    lines = [
        f"## 第 {episode['order']} 集《{episode['title']}》",
        "",
        f"分镜概述：{storyboard['summary']}",
        "",
    ]
    for shot in storyboard["shots"]:
        lines.extend(
            [
                f"### 镜头 {shot['order']}｜{shot['shot_size']}｜{shot['duration_sec']} 秒｜{shot['location']}",
                "",
                f"- 运镜：{shot['camera_move']}",
                f"- 人物：{'、'.join(shot['character_refs']) if shot['character_refs'] else '无'}",
                f"- 动作：{shot['action']}",
            ]
        )
        if shot["dialogue"]:
            lines.append(f"- 对白：{shot['dialogue']}")
        lines.extend([f"- 画面：{shot['visual_prompt']}", ""])
    return "\n".join(lines)


def render_storyboard_file(root: Path, state: dict[str, Any], episode_order: int) -> None:
    storyboard = find_item(state["storyboards"], episode_order)
    episode = find_item(state["episodes"], episode_order)
    if not storyboard or not episode:
        return
    atomic_write(
        root / "storyboards" / f"{episode_order:02d}.json",
        json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n",
    )
    atomic_write(
        root / "storyboards" / f"{episode_order:02d}.md",
        storyboard_markdown(episode, storyboard) + "\n",
    )


def build_combined_storyboard(root: Path, state: dict[str, Any]) -> None:
    if not state.get("adaptation") or not state.get("episodes"):
        return
    lines = [f"# 短剧分镜：{state['adaptation']['title']}", ""]
    for episode in state["episodes"]:
        storyboard = find_item(state["storyboards"], episode["order"])
        if storyboard:
            lines.extend([storyboard_markdown(episode, storyboard), ""])
        else:
            lines.extend(
                [
                    f"## 第 {episode['order']} 集《{episode['title']}》",
                    "",
                    "尚未生成分镜。",
                    "",
                ]
            )
    atomic_write(root / "storyboard.md", "\n".join(lines).rstrip() + "\n")


def check_state(root: Path, state: dict[str, Any]) -> None:
    snapshot = root / SOURCE_SNAPSHOT
    if not snapshot.exists():
        raise SkillError("Missing source.story.md snapshot")
    if sha256_text(read_text(snapshot)) != state["source"]["snapshot_sha256"]:
        raise SkillError("source.story.md does not match its recorded snapshot hash")
    if any(state.get(field) for field in ("episodes", "scripts", "qualities", "storyboards")) and not state.get("adaptation"):
        raise SkillError("Adaptation contract is required once downstream artifacts exist")
    if state.get("adaptation"):
        adaptation_contract(state["adaptation"], state["settings"]["episodes"])
    if state.get("episodes"):
        episodes_contract(
            {"episodes": state["episodes"]},
            state["settings"]["episodes"],
            state["settings"]["episode_seconds"],
        )
    for script in state.get("scripts", []):
        script_contract(script)
    for quality in state.get("qualities", []):
        episode = find_item(state["episodes"], quality["order"])
        if not episode:
            raise SkillError(f"Quality references unknown episode {quality['order']}")
        quality_contract(
            quality,
            episode,
            (state.get("adaptation") or {}).get("paywall_plan"),
        )
    names = {
        item["name"]
        for item in (state.get("adaptation") or {}).get("characters", [])
    }
    for storyboard in state.get("storyboards", []):
        storyboard_contract(storyboard, names)


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    if (root / STATE_FILE).exists():
        raise SkillError(f"{root / STATE_FILE} already exists; resume instead of reinitializing")
    source_path = Path(args.source).expanduser().resolve()
    content = read_text(source_path)
    chars = visible_chars(content)
    if not MIN_SOURCE_CHARS <= chars <= MAX_SOURCE_CHARS:
        raise SkillError(
            f"Source must contain {MIN_SOURCE_CHARS}-{MAX_SOURCE_CHARS} non-whitespace characters; found {chars}"
        )
    episodes = require_int(args.episodes, "--episodes", 1, MAX_EPISODES)
    episode_seconds = require_int(args.episode_seconds, "--episode-seconds", 20, 300)
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("scripts", "quality", "storyboards"):
        (root / folder).mkdir(exist_ok=True)
    snapshot_hash = sha256_text(content)
    stamp = now_iso()
    state: dict[str, Any] = {
        "schema_version": 1,
        "status": "source_ready",
        "source": {
            "path": str(source_path),
            "title": args.title or source_title(content, source_path.stem),
            "characters": chars,
            "source_sha256": snapshot_hash,
            "snapshot_sha256": snapshot_hash,
        },
        "settings": {
            "episodes": episodes,
            "episode_seconds": episode_seconds,
            "aspect_ratio": args.aspect_ratio,
        },
        "adaptation": None,
        "episodes": [],
        "scripts": [],
        "qualities": [],
        "storyboards": [],
        "created_at": stamp,
        "updated_at": stamp,
    }
    atomic_write(root / SOURCE_SNAPSHOT, content)
    save_state(root, state)
    return {"status": "ok", "root": str(root), "source_chars": chars, "episode_count": episodes}


def command_check_source(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    return {"status": "ok", **source_status(root, state)}


def command_save_adaptation(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    if state.get("episodes"):
        raise SkillError("Cannot replace the adaptation after episodes have been created")
    raw = read_json(Path(args.input).expanduser().resolve())
    adaptation = adaptation_contract(raw, state["settings"]["episodes"])
    state["adaptation"] = adaptation
    state["status"] = "adaptation_ready"
    save_state(root, state)
    render_adaptation(root, state)
    return {"status": "ok", "title": adaptation["title"], "characters": len(adaptation["characters"])}


def command_save_episodes(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    if not state.get("adaptation"):
        raise SkillError("Save the adaptation contract before creating episodes")
    if state.get("scripts"):
        raise SkillError("Cannot replace the episode outline after scripts have been created")
    raw = read_json(Path(args.input).expanduser().resolve())
    episodes = episodes_contract(
        raw,
        state["settings"]["episodes"],
        state["settings"]["episode_seconds"],
    )
    paywall_plan = state["adaptation"].get("paywall_plan")
    if paywall_plan:
        first = paywall_plan["first_paywall_at"]
        for episode in episodes:
            if episode["is_paywall"] and episode["order"] < first:
                raise SkillError("No episode may be marked paywall before first_paywall_at")
        if not find_item(episodes, first)["is_paywall"]:
            raise SkillError("The first_paywall_at episode must be marked is_paywall=true")
    state["episodes"] = episodes
    state["status"] = "episodes_ready"
    save_state(root, state)
    render_episodes(root, state)
    build_combined_storyboard(root, state)
    return {"status": "ok", "episode_count": len(episodes)}


def command_save_script(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    if not state.get("episodes"):
        raise SkillError("Save the episode outline before writing scripts")
    episode = find_item(state["episodes"], args.episode)
    if not episode:
        raise SkillError(f"Unknown episode: {args.episode}")
    existing = find_item(state["scripts"], args.episode)
    if existing:
        raise SkillError(
            f"Episode {args.episode} already has a script; use repair-script only when the quality gate requires it"
        )
    next_order = next(
        (item["order"] for item in state["episodes"] if not find_item(state["scripts"], item["order"])),
        None,
    )
    if args.episode != next_order:
        raise SkillError(f"Sequential scripting required; next episode is {next_order}")
    script = script_contract(read_json(Path(args.input).expanduser().resolve()))
    script.update(
        {
            "order": args.episode,
            "repair_attempted": False,
            "version": 1,
        }
    )
    state["scripts"].append(script)
    state["scripts"].sort(key=lambda item: item["order"])
    state["status"] = "scripting"
    save_state(root, state)
    render_script_file(root, state, args.episode)
    return {
        "status": "ok",
        "episode": args.episode,
        "duration_sec": script["duration_sec"],
        "script_chars": visible_chars(script["content"]),
    }


def command_save_quality(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    episode = find_item(state["episodes"], args.episode)
    script = find_item(state["scripts"], args.episode)
    if not episode or not script:
        raise SkillError(f"Episode {args.episode} needs both an outline and a script before review")
    raw = read_json(Path(args.input).expanduser().resolve())
    quality = quality_contract(
        raw,
        episode,
        (state.get("adaptation") or {}).get("paywall_plan"),
    )
    quality["order"] = args.episode
    quality["checked_at"] = now_iso()
    state["qualities"] = [
        item for item in state["qualities"] if item["order"] != args.episode
    ]
    state["qualities"].append(quality)
    state["qualities"].sort(key=lambda item: item["order"])
    state["status"] = (
        "reviewed"
        if quality["status"] in {"approved", "continue_with_warning"}
        else "needs_repair"
    )
    save_state(root, state)
    render_quality_file(root, state, args.episode)
    return {
        "status": "ok",
        "episode": args.episode,
        "quality_status": quality["status"],
        "overall": quality["score"]["overall"],
        "issue_count": len(quality["flags"]),
    }


def command_repair_script(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    script = find_item(state["scripts"], args.episode)
    quality = find_item(state["qualities"], args.episode)
    if not script:
        raise SkillError(f"Episode {args.episode} needs a script before repair")
    if script.get("repair_attempted"):
        raise SkillError("The one permitted automatic repair for this episode has already been used")
    if not quality:
        raise SkillError(f"Episode {args.episode} needs a quality result before repair")
    if quality["status"] not in {"repairable", "blocked"}:
        raise SkillError("Script repair is only allowed after a repairable or blocked review")
    replacement = script_contract(read_json(Path(args.input).expanduser().resolve()))
    script.update(replacement)
    script["repair_attempted"] = True
    script["version"] = int(script.get("version", 1)) + 1
    state["qualities"] = [
        item for item in state["qualities"] if item["order"] != args.episode
    ]
    state["status"] = "repair_applied"
    save_state(root, state)
    render_script_file(root, state, args.episode)
    quality_path = root / "quality" / f"{args.episode:02d}.json"
    if quality_path.exists():
        quality_path.unlink()
    return {"status": "ok", "episode": args.episode, "review_required": True}


def command_save_storyboard(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    episode = find_item(state["episodes"], args.episode)
    script = find_item(state["scripts"], args.episode)
    quality = find_item(state["qualities"], args.episode)
    if not episode or not script:
        raise SkillError(f"Episode {args.episode} needs an outline and script")
    if not quality or quality["status"] not in {"approved", "continue_with_warning"}:
        raise SkillError("A current approved or continue_with_warning review is required before storyboard")
    character_names = {
        item["name"] for item in state["adaptation"]["characters"]
    }
    storyboard = storyboard_contract(
        read_json(Path(args.input).expanduser().resolve()), character_names
    )
    storyboard.update(
        {
            "order": args.episode,
            "estimated_duration_sec": sum(
                shot["duration_sec"] for shot in storyboard["shots"]
            ),
            "version": (
                int(find_item(state["storyboards"], args.episode).get("version", 0)) + 1
                if find_item(state["storyboards"], args.episode)
                else 1
            ),
        }
    )
    state["storyboards"] = [
        item for item in state["storyboards"] if item["order"] != args.episode
    ]
    state["storyboards"].append(storyboard)
    state["storyboards"].sort(key=lambda item: item["order"])
    state["status"] = "storyboarding"
    save_state(root, state)
    render_storyboard_file(root, state, args.episode)
    build_combined_storyboard(root, state)
    return {
        "status": "ok",
        "episode": args.episode,
        "shot_count": len(storyboard["shots"]),
        "estimated_duration_sec": storyboard["estimated_duration_sec"],
    }


def command_finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_source_usable(root, state)
    if not state.get("adaptation"):
        raise SkillError("Save the adaptation contract before finalizing")
    if not state.get("episodes"):
        raise SkillError("Save the episode outline before finalizing")
    missing_scripts = [
        episode["order"]
        for episode in state["episodes"]
        if not find_item(state["scripts"], episode["order"])
    ]
    if missing_scripts:
        raise SkillError(f"Missing episode scripts: {missing_scripts}")
    unacceptable_quality = [
        episode["order"]
        for episode in state["episodes"]
        if (
            not find_item(state["qualities"], episode["order"])
            or find_item(state["qualities"], episode["order"])["status"]
            not in {"approved", "continue_with_warning"}
        )
    ]
    if unacceptable_quality:
        raise SkillError(f"Episodes not ready for storyboard: {unacceptable_quality}")
    missing_storyboards = [
        episode["order"]
        for episode in state["episodes"]
        if not find_item(state["storyboards"], episode["order"])
    ]
    if missing_storyboards:
        raise SkillError(f"Missing episode storyboards: {missing_storyboards}")
    state["status"] = "completed"
    save_state(root, state)
    build_combined_storyboard(root, state)
    return {
        "status": "ok",
        "title": state["adaptation"]["title"],
        "episode_count": len(state["episodes"]),
        "storyboard_path": str(root / "storyboard.md"),
        "warnings": [
            item["order"]
            for item in state["qualities"]
            if item["status"] == "continue_with_warning"
        ],
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    source = source_status(root, state)
    return {
        "status": "ok",
        "workflow_status": state["status"],
        "title": (state.get("adaptation") or {}).get("title") or state["source"]["title"],
        "source_available": source["source_available"],
        "source_changed": source["source_changed"],
        "snapshot_valid": source["snapshot_valid"],
        "target_episodes": state["settings"]["episodes"],
        "episodes_planned": len(state.get("episodes", [])),
        "scripts": len(state.get("scripts", [])),
        "quality_approved": sum(
            1
            for item in state.get("qualities", [])
            if item["status"] in {"approved", "continue_with_warning"}
        ),
        "storyboards": len(state.get("storyboards", [])),
    }


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    check_state(root, state)
    source = source_status(root, state)
    return {
        "status": "ok",
        "message": "State is structurally valid",
        "source_changed": source["source_changed"],
        "workflow_status": state["status"],
    }


def command_build(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    check_state(root, state)
    render_adaptation(root, state)
    render_episodes(root, state)
    for script in state.get("scripts", []):
        render_script_file(root, state, script["order"])
    for quality in state.get("qualities", []):
        render_quality_file(root, state, quality["order"])
    for storyboard in state.get("storyboards", []):
        render_storyboard_file(root, state, storyboard["order"])
    build_combined_storyboard(root, state)
    return {"status": "ok", "storyboard_path": str(root / "storyboard.md")}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage short-story-to-drama adaptation and storyboard state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a drama project from a short story")
    init_parser.add_argument("root")
    init_parser.add_argument("--source", required=True, help="Source story.md")
    init_parser.add_argument("--episodes", required=True, type=int)
    init_parser.add_argument("--episode-seconds", required=True, type=int)
    init_parser.add_argument("--aspect-ratio", default="9:16")
    init_parser.add_argument("--title")
    init_parser.set_defaults(handler=command_init)

    for name, handler, help_text in [
        ("check-source", command_check_source, "Compare the original source with its snapshot"),
        ("status", command_status, "Show stage and artifact counts"),
        ("validate", command_validate, "Validate state and snapshot integrity"),
        ("finalize", command_finalize, "Validate and build the final combined storyboard"),
        ("build", command_build, "Rebuild readable output files"),
    ]:
        command_parser = subparsers.add_parser(name, help=help_text)
        command_parser.add_argument("root")
        command_parser.set_defaults(handler=handler)

    adaptation_parser = subparsers.add_parser("save-adaptation", help="Save the adaptation contract")
    adaptation_parser.add_argument("root")
    adaptation_parser.add_argument("--input", required=True)
    adaptation_parser.set_defaults(handler=command_save_adaptation)

    episodes_parser = subparsers.add_parser("save-episodes", help="Save the full episode outline")
    episodes_parser.add_argument("root")
    episodes_parser.add_argument("--input", required=True)
    episodes_parser.set_defaults(handler=command_save_episodes)

    script_parser = subparsers.add_parser("save-script", help="Save the next episode script")
    script_parser.add_argument("root")
    script_parser.add_argument("--episode", required=True, type=int)
    script_parser.add_argument("--input", required=True)
    script_parser.set_defaults(handler=command_save_script)

    quality_parser = subparsers.add_parser("save-quality", help="Save an episode quality result")
    quality_parser.add_argument("root")
    quality_parser.add_argument("--episode", required=True, type=int)
    quality_parser.add_argument("--input", required=True)
    quality_parser.set_defaults(handler=command_save_quality)

    repair_parser = subparsers.add_parser("repair-script", help="Apply one repair to an episode script")
    repair_parser.add_argument("root")
    repair_parser.add_argument("--episode", required=True, type=int)
    repair_parser.add_argument("--input", required=True)
    repair_parser.set_defaults(handler=command_repair_script)

    storyboard_parser = subparsers.add_parser("save-storyboard", help="Save one episode storyboard")
    storyboard_parser.add_argument("root")
    storyboard_parser.add_argument("--episode", required=True, type=int)
    storyboard_parser.add_argument("--input", required=True)
    storyboard_parser.set_defaults(handler=command_save_storyboard)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except SkillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
