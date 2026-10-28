#!/usr/bin/env python3
"""File-backed state manager for the ai-novel-short-story skill."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_FILE = "state.json"
MIN_CHARS = 3_000
MAX_CHARS = 30_000
MIN_ACCEPT_RATIO = 0.70


class SkillError(Exception):
    """A user-correctable workflow error."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def char_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def require_text(value: Any, field: str, *, minimum: int = 1) -> str:
    if not isinstance(value, str):
        raise SkillError(f"{field} must be a string")
    cleaned = value.strip()
    if len(cleaned) < minimum:
        raise SkillError(f"{field} must contain at least {minimum} characters")
    return cleaned


def require_text_list(value: Any, field: str, *, minimum: int, maximum: int) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise SkillError(f"{field} must contain {minimum}-{maximum} items")
    return [require_text(item, f"{field}[{index}]", minimum=2) for index, item in enumerate(value)]


def require_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SkillError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise SkillError(f"{field} must be between {minimum} and {maximum}")
    return value


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SkillError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SkillError(f"Expected a JSON object in {path}")
    return value


def save_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    atomic_write(root / STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def load_state(root: Path) -> dict[str, Any]:
    state = read_json(root / STATE_FILE)
    if state.get("schema_version") != 1:
        raise SkillError("Unsupported state schema; expected schema_version 1")
    return state


def total_chars(state: dict[str, Any]) -> int:
    return sum(char_count(segment.get("content", "")) for segment in state["segments"])


def build_story(root: Path, state: dict[str, Any]) -> int:
    pieces = [
        segment["content"].strip()
        for segment in state["segments"]
        if segment.get("content", "").strip()
    ]
    content = "\n\n".join(pieces).strip()
    if content:
        content += "\n"
    atomic_write(root / "story.md", content)
    return char_count(content)


def render_intent(root: Path, state: dict[str, Any]) -> None:
    lines = [
        "# 创作意图",
        "",
        f"- 目标字数：{state['target_word_count']}",
        f"- 平台：{state['platform']}",
        f"- 当前状态：{state['status']}",
        "",
        "## 用户原始想法",
        "",
        state["original_idea"],
        "",
        "## AI 理解",
        "",
        state.get("understanding") or "待生成创作方向时补充。",
        "",
    ]
    atomic_write(root / "intent.md", "\n".join(lines))


def render_directions(root: Path, state: dict[str, Any]) -> None:
    lines = ["# 创作方向", "", f"## 理解", "", state["understanding"], ""]
    for index, direction in enumerate(state["directions"], start=1):
        selected = "（已选择）" if direction["id"] == state.get("selected_direction_id") else ""
        lines.extend(
            [
                f"## 方向 {index}：{direction['title']} {selected}".rstrip(),
                "",
                f"- ID：`{direction['id']}`",
                f"- 核心体验：{direction['core_experience']}",
                f"- 主角：{direction['protagonist']}",
                f"- 核心冲突：{direction['central_conflict']}",
                f"- 结局承诺：{direction['ending_promise']}",
                f"- 风格关键词：{'、'.join(direction['style_keywords'])}",
                "",
                direction["premise"],
                "",
            ]
        )
    atomic_write(root / "directions.md", "\n".join(lines))


def render_plan(root: Path, state: dict[str, Any]) -> None:
    plan = state["plan"]
    contract = plan["causal_contract"]
    lines = [
        f"# {plan['title']}",
        "",
        f"- 目标字数：{plan['target_word_count']}",
        f"- 内部片段数：{len(plan['segments'])}",
        f"- 结局承诺：{plan['ending_promise']}",
        "",
        "## 因果契约",
        "",
        f"- 主角目标：{contract['protagonist_goal']}",
        f"- 核心问题：{contract['central_question']}",
        "",
        "### 固定事实",
        "",
    ]
    lines.extend(f"- {item}" for item in contract["fixed_facts"])
    lines.extend(["", "### 因果链", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(contract["cause_effect_chain"], 1))
    lines.extend(["", "### 铺垫与兑现", ""])
    lines.extend(
        f"- 片段 {item['setup_segment_order']}：{item['setup']} → 片段 {item['payoff_segment_order']}：{item['payoff']}"
        for item in contract["setup_payoffs"]
    )
    for segment in plan["segments"]:
        lines.extend(
            [
                "",
                f"## 片段 {segment['order']}",
                "",
                f"- 功能：{segment['purpose']}",
                f"- 目标字数：{segment['target_word_count']}",
                f"- 开场状态：{segment['opening_state']}",
                f"- 开篇钩子：{segment['opening_hook']}",
                f"- 即时目标：{segment['immediate_goal']}",
                f"- 转折：{segment['turning_point']}",
                f"- 题材回报：{segment['payoff']}",
                f"- 片尾牵引：{segment['closing_pull']}",
                f"- 结束状态：{segment['closing_state']}",
                "",
                "### 推进节拍",
                "",
            ]
        )
        lines.extend(
            f"{index}. {beat}"
            for index, beat in enumerate(segment["progression_beats"], 1)
        )
    lines.append("")
    atomic_write(root / "plan.md", "\n".join(lines))


def render_review(root: Path, state: dict[str, Any]) -> None:
    audit = state.get("audit")
    lines = ["# 全篇审校", ""]
    if not audit:
        lines.append("尚未执行全篇审校。")
    else:
        lines.extend(
            [
                f"- 判定：{audit['decision']}",
                f"- 总结：{audit['summary']}",
                "",
                "## 问题",
                "",
            ]
        )
        if audit["issues"]:
            for issue in audit["issues"]:
                affected = "、".join(str(order) for order in issue["affected_segment_orders"]) or "全篇"
                lines.append(
                    f"- [{issue['severity']}] `{issue['code']}`（片段 {affected}）：{issue['description']}"
                )
                if issue.get("repair_instruction"):
                    lines.append(f"  - 修复方向：{issue['repair_instruction']}")
        else:
            lines.append("- 无。")
    repair = state.get("repair")
    if repair:
        lines.extend(
            [
                "",
                "## 必要修复",
                "",
                f"- 已替换片段：{'、'.join(str(order) for order in repair['patched_orders'])}",
            ]
        )
        if repair["residual_quality_debt"]:
            lines.append("- 残余质量债务：")
            lines.extend(f"  - {item}" for item in repair["residual_quality_debt"])
        else:
            lines.append("- 残余质量债务：无。")
    lines.append("")
    atomic_write(root / "review.md", "\n".join(lines))


def direction_contract(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError(f"directions[{index}] must be an object")
    direction = {
        "id": require_text(raw.get("id"), f"directions[{index}].id"),
        "title": require_text(raw.get("title"), f"directions[{index}].title"),
        "premise": require_text(raw.get("premise"), f"directions[{index}].premise", minimum=10),
        "core_experience": require_text(
            raw.get("core_experience"), f"directions[{index}].core_experience", minimum=4
        ),
        "protagonist": require_text(
            raw.get("protagonist"), f"directions[{index}].protagonist", minimum=4
        ),
        "central_conflict": require_text(
            raw.get("central_conflict"), f"directions[{index}].central_conflict", minimum=4
        ),
        "ending_promise": require_text(
            raw.get("ending_promise"), f"directions[{index}].ending_promise", minimum=4
        ),
        "style_keywords": require_text_list(
            raw.get("style_keywords"),
            f"directions[{index}].style_keywords",
            minimum=2,
            maximum=8,
        ),
    }
    return direction


def plan_contract(raw: Any, target_word_count: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("plan input must be a JSON object")
    title = require_text(raw.get("title"), "plan.title")
    plan_target = require_int(
        raw.get("target_word_count"),
        "plan.target_word_count",
        minimum=MIN_CHARS,
        maximum=MAX_CHARS,
    )
    if plan_target != target_word_count:
        raise SkillError(
            f"plan.target_word_count ({plan_target}) must equal the confirmed target ({target_word_count})"
        )
    ending_promise = require_text(raw.get("ending_promise"), "plan.ending_promise", minimum=4)
    raw_segments = raw.get("segments")
    if not isinstance(raw_segments, list) or not 2 <= len(raw_segments) <= 8:
        raise SkillError("plan.segments must contain 2-8 items")

    segments: list[dict[str, Any]] = []
    for index, raw_segment in enumerate(raw_segments, start=1):
        if not isinstance(raw_segment, dict):
            raise SkillError(f"plan.segments[{index - 1}] must be an object")
        expected_order = len(segments) + 1
        order = require_int(
            raw_segment.get("order"),
            f"plan.segments[{index - 1}].order",
            minimum=1,
            maximum=8,
        )
        if order != expected_order:
            raise SkillError("plan segment orders must be consecutive starting at 1")
        segment = {
            "order": order,
            "purpose": require_text(
                raw_segment.get("purpose"), f"segment[{order}].purpose", minimum=4
            ),
            "target_word_count": require_int(
                raw_segment.get("target_word_count"),
                f"segment[{order}].target_word_count",
                minimum=300,
                maximum=15_000,
            ),
            "opening_state": require_text(
                raw_segment.get("opening_state"), f"segment[{order}].opening_state", minimum=2
            ),
            "opening_hook": require_text(
                raw_segment.get("opening_hook"), f"segment[{order}].opening_hook", minimum=4
            ),
            "immediate_goal": require_text(
                raw_segment.get("immediate_goal"), f"segment[{order}].immediate_goal", minimum=4
            ),
            "progression_beats": require_text_list(
                raw_segment.get("progression_beats"),
                f"segment[{order}].progression_beats",
                minimum=2,
                maximum=6,
            ),
            "turning_point": require_text(
                raw_segment.get("turning_point"), f"segment[{order}].turning_point", minimum=2
            ),
            "payoff": require_text(
                raw_segment.get("payoff"), f"segment[{order}].payoff", minimum=4
            ),
            "closing_pull": require_text(
                raw_segment.get("closing_pull"), f"segment[{order}].closing_pull", minimum=4
            ),
            "closing_state": require_text(
                raw_segment.get("closing_state"), f"segment[{order}].closing_state", minimum=2
            ),
        }
        segments.append(segment)

    tolerance = max(500, round(target_word_count * 0.08))
    segment_budget = sum(segment["target_word_count"] for segment in segments)
    if abs(segment_budget - target_word_count) > tolerance:
        raise SkillError(
            f"segment target total ({segment_budget}) must be within {tolerance} of {target_word_count}"
        )

    raw_contract = raw.get("causal_contract")
    if not isinstance(raw_contract, dict):
        raise SkillError("plan.causal_contract is required")
    fixed_facts = require_text_list(
        raw_contract.get("fixed_facts"), "causal_contract.fixed_facts", minimum=3, maximum=12
    )
    cause_effect_chain = require_text_list(
        raw_contract.get("cause_effect_chain"),
        "causal_contract.cause_effect_chain",
        minimum=3,
        maximum=8,
    )
    raw_payoffs = raw_contract.get("setup_payoffs")
    if not isinstance(raw_payoffs, list) or not 2 <= len(raw_payoffs) <= 8:
        raise SkillError("causal_contract.setup_payoffs must contain 2-8 items")
    setup_payoffs: list[dict[str, Any]] = []
    segment_count = len(segments)
    for index, raw_item in enumerate(raw_payoffs):
        if not isinstance(raw_item, dict):
            raise SkillError(f"setup_payoffs[{index}] must be an object")
        setup_order = require_int(
            raw_item.get("setup_segment_order"),
            f"setup_payoffs[{index}].setup_segment_order",
            minimum=1,
            maximum=segment_count,
        )
        payoff_order = require_int(
            raw_item.get("payoff_segment_order"),
            f"setup_payoffs[{index}].payoff_segment_order",
            minimum=1,
            maximum=segment_count,
        )
        if setup_order >= payoff_order:
            raise SkillError(
                f"setup_payoffs[{index}] must be planted before it is paid off"
            )
        setup_payoffs.append(
            {
                "setup": require_text(
                    raw_item.get("setup"), f"setup_payoffs[{index}].setup", minimum=4
                ),
                "setup_segment_order": setup_order,
                "payoff": require_text(
                    raw_item.get("payoff"), f"setup_payoffs[{index}].payoff", minimum=4
                ),
                "payoff_segment_order": payoff_order,
            }
        )

    causal_contract = {
        "protagonist_goal": require_text(
            raw_contract.get("protagonist_goal"),
            "causal_contract.protagonist_goal",
            minimum=4,
        ),
        "central_question": require_text(
            raw_contract.get("central_question"),
            "causal_contract.central_question",
            minimum=4,
        ),
        "fixed_facts": fixed_facts,
        "cause_effect_chain": cause_effect_chain,
        "setup_payoffs": setup_payoffs,
    }
    return {
        "title": title,
        "target_word_count": plan_target,
        "ending_promise": ending_promise,
        "segments": segments,
        "causal_contract": causal_contract,
    }


def audit_contract(raw: Any, total_word_count: int, target_word_count: int, segments: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SkillError("audit input must be a JSON object")
    decision = raw.get("decision")
    if decision not in {"accepted", "patchable", "replan_required"}:
        raise SkillError("audit.decision must be accepted, patchable, or replan_required")
    summary = require_text(raw.get("summary"), "audit.summary", minimum=4)
    raw_issues = raw.get("issues", [])
    if not isinstance(raw_issues, list) or len(raw_issues) > 20:
        raise SkillError("audit.issues must be a list with at most 20 items")
    segment_count = len(segments)
    issues: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_issues):
        if not isinstance(raw_item, dict):
            raise SkillError(f"audit.issues[{index}] must be an object")
        severity = raw_item.get("severity", "standard")
        if severity not in {"critical", "standard"}:
            raise SkillError(f"audit.issues[{index}].severity must be critical or standard")
        raw_orders = raw_item.get("affected_segment_orders", [])
        if not isinstance(raw_orders, list) or len(raw_orders) > 8:
            raise SkillError(
                f"audit.issues[{index}].affected_segment_orders must be a list with at most 8 items"
            )
        orders = [
            require_int(order, f"audit.issues[{index}].affected_segment_orders", minimum=1, maximum=segment_count)
            for order in raw_orders
        ]
        issue = {
            "code": require_text(raw_item.get("code"), f"audit.issues[{index}].code"),
            "severity": severity,
            "description": require_text(
                raw_item.get("description"), f"audit.issues[{index}].description", minimum=4
            ),
            "affected_segment_orders": orders,
        }
        if raw_item.get("repair_instruction") is not None:
            issue["repair_instruction"] = require_text(
                raw_item.get("repair_instruction"),
                f"audit.issues[{index}].repair_instruction",
                minimum=4,
            )
        issues.append(issue)

    if decision == "accepted" and total_word_count < round(target_word_count * MIN_ACCEPT_RATIO):
        raise SkillError("A story below 70% of target length cannot be accepted")
    if decision == "accepted" and any(issue["severity"] == "critical" for issue in issues):
        raise SkillError("A story with critical issues cannot be accepted")
    return {"decision": decision, "summary": summary, "issues": issues}


def ensure_complete_segments(state: dict[str, Any]) -> None:
    if not state.get("segments"):
        raise SkillError("No segments exist; save the plan first")
    pending = [segment["order"] for segment in state["segments"] if segment["status"] != "completed"]
    if pending:
        raise SkillError(f"Pending segments must be completed first: {pending}")


def check_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("original_idea"):
        raise SkillError("State is missing original_idea")
    if state.get("selected_direction_id") and state.get("direction"):
        if state["direction"].get("id") != state["selected_direction_id"]:
            raise SkillError("Selected direction does not match direction snapshot")
    if state.get("plan"):
        plan_contract(state["plan"], state["target_word_count"])
        if [segment["order"] for segment in state["segments"]] != [
            segment["order"] for segment in state["plan"]["segments"]
        ]:
            raise SkillError("State segments do not match the plan")
    if state.get("audit"):
        audit_contract(
            state["audit"],
            total_chars(state),
            state["target_word_count"],
            state["segments"],
        )
    return state


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    if (root / STATE_FILE).exists():
        raise SkillError(f"{root / STATE_FILE} already exists; resume instead of reinitializing")
    idea = require_text(args.idea, "--idea", minimum=10)
    target = require_int(args.target, "--target", minimum=MIN_CHARS, maximum=MAX_CHARS)
    platform = require_text(args.platform, "--platform")
    root.mkdir(parents=True, exist_ok=True)
    (root / "segments").mkdir(exist_ok=True)
    stamp = now_iso()
    state: dict[str, Any] = {
        "schema_version": 1,
        "status": "intake",
        "title": "",
        "original_idea": idea,
        "understanding": "",
        "platform": platform,
        "target_word_count": target,
        "directions": [],
        "selected_direction_id": None,
        "direction": None,
        "plan": None,
        "segments": [],
        "audit": None,
        "repair": None,
        "repair_attempted": False,
        "quality_debt": [],
        "created_at": stamp,
        "updated_at": stamp,
    }
    save_state(root, state)
    render_intent(root, state)
    return {"status": "ok", "root": str(root), "state": state}


def command_set_directions(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    if state.get("plan"):
        raise SkillError("Cannot replace directions after a plan has been created")
    raw = read_json(Path(args.input).expanduser().resolve())
    understanding = require_text(raw.get("understanding"), "understanding", minimum=10)
    raw_directions = raw.get("directions")
    if not isinstance(raw_directions, list) or len(raw_directions) != 3:
        raise SkillError("directions must contain exactly three items")
    directions = [direction_contract(item, index) for index, item in enumerate(raw_directions)]
    for field in ("id", "title", "premise"):
        values = [direction[field] for direction in directions]
        if len(set(values)) != len(values):
            raise SkillError(f"The three directions must each have a unique {field}")
    material_differences = {
        (
            direction["core_experience"],
            direction["central_conflict"],
            direction["ending_promise"],
        )
        for direction in directions
    }
    if len(material_differences) != 3:
        raise SkillError(
            "The three directions must differ materially in core experience, conflict, or ending payoff"
        )
    state["understanding"] = understanding
    state["directions"] = directions
    state["recommendation_reason"] = require_text(
        raw.get("recommendation_reason"), "recommendation_reason", minimum=10
    )
    if raw.get("platform"):
        state["platform"] = require_text(raw.get("platform"), "platform")
    if raw.get("platform_reason"):
        state["platform_reason"] = require_text(raw.get("platform_reason"), "platform_reason", minimum=10)
    state["status"] = "directions_ready"
    save_state(root, state)
    render_intent(root, state)
    render_directions(root, state)
    return {"status": "ok", "directions": directions}


def command_choose_direction(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    if state.get("plan"):
        raise SkillError("Cannot change direction after a plan has been created")
    selected = next((item for item in state.get("directions", []) if item["id"] == args.id), None)
    if not selected:
        available = [item["id"] for item in state.get("directions", [])]
        raise SkillError(f"Unknown direction id {args.id!r}; available: {available}")
    state["selected_direction_id"] = selected["id"]
    state["direction"] = selected
    state["status"] = "direction_selected"
    save_state(root, state)
    render_directions(root, state)
    return {"status": "ok", "direction": selected}


def command_set_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    if not state.get("direction"):
        raise SkillError("Choose a direction before creating the plan")
    if state.get("plan"):
        raise SkillError("A plan already exists; use a revision flow instead of replacing it blindly")
    plan = plan_contract(read_json(Path(args.input).expanduser().resolve()), state["target_word_count"])
    state["title"] = plan["title"]
    state["plan"] = plan
    state["segments"] = [
        {
            "order": segment["order"],
            "target_word_count": segment["target_word_count"],
            "content": "",
            "continuity_summary": "",
            "status": "pending",
            "human_edited": False,
            "version": 0,
        }
        for segment in plan["segments"]
    ]
    state["status"] = "planned"
    save_state(root, state)
    render_plan(root, state)
    build_story(root, state)
    return {"status": "ok", "plan": plan, "segment_count": len(plan["segments"])}


def segment_input(path: str) -> tuple[str, str]:
    raw = read_json(Path(path).expanduser().resolve())
    content = require_text(raw.get("content"), "content", minimum=200)
    continuity = require_text(raw.get("continuity_summary"), "continuity_summary", minimum=10)
    return content, continuity


def command_save_segment(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    if not state.get("plan"):
        raise SkillError("No plan exists")
    segment = next((item for item in state["segments"] if item["order"] == args.order), None)
    if not segment:
        raise SkillError(f"Unknown segment order: {args.order}")
    pending_order = next(
        (item["order"] for item in state["segments"] if item["status"] != "completed"),
        None,
    )
    if pending_order is None:
        raise SkillError("All segments are already complete; use edit-segment or repair")
    if args.order != pending_order:
        raise SkillError(f"Sequential drafting required; next segment is {pending_order}")
    content, continuity = segment_input(args.input)
    segment["content"] = content
    segment["continuity_summary"] = continuity
    segment["status"] = "completed"
    segment["human_edited"] = False
    segment["version"] = int(segment.get("version", 0)) + 1
    state["status"] = "drafting"
    save_state(root, state)
    atomic_write(root / "segments" / f"{args.order:02d}.md", content.strip() + "\n")
    word_count = build_story(root, state)
    return {
        "status": "ok",
        "order": args.order,
        "segment_char_count": char_count(content),
        "story_char_count": word_count,
    }


def command_edit_segment(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    segment = next((item for item in state["segments"] if item["order"] == args.order), None)
    if not segment or segment["status"] != "completed":
        raise SkillError(f"Segment {args.order} is not completed")
    if segment.get("human_edited") and not args.replace_human:
        raise SkillError(
            "This segment was already human-edited; pass --replace-human only after explicit user consent"
        )
    content, continuity = segment_input(args.input)
    segment["content"] = content
    segment["continuity_summary"] = continuity
    segment["human_edited"] = True
    segment["version"] = int(segment.get("version", 0)) + 1
    state["status"] = "edited"
    save_state(root, state)
    atomic_write(root / "segments" / f"{args.order:02d}.md", content.strip() + "\n")
    word_count = build_story(root, state)
    return {
        "status": "ok",
        "order": args.order,
        "segment_char_count": char_count(content),
        "story_char_count": word_count,
        "human_edited": True,
    }


def command_audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_complete_segments(state)
    story_path = root / "story.md"
    story_chars = build_story(root, state)
    if not story_path.exists():
        raise SkillError("story.md was not generated")
    raw_audit = read_json(Path(args.input).expanduser().resolve())
    audit = audit_contract(raw_audit, story_chars, state["target_word_count"], state["segments"])
    state["audit"] = audit
    if audit["decision"] == "accepted":
        state["status"] = "review_passed"
    elif audit["decision"] == "patchable":
        state["status"] = "needs_repair"
    else:
        state["status"] = "replan_required"
    save_state(root, state)
    render_review(root, state)
    return {
        "status": "ok",
        "decision": audit["decision"],
        "story_char_count": story_chars,
        "issue_count": len(audit["issues"]),
    }


def command_repair(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    audit = state.get("audit")
    if not audit or audit["decision"] != "patchable":
        raise SkillError("A one-pass repair is allowed only after a patchable audit")
    if state.get("repair_attempted"):
        raise SkillError("The one permitted repair has already been applied")
    raw = read_json(Path(args.input).expanduser().resolve())
    raw_patches = raw.get("patches")
    if not isinstance(raw_patches, list) or not 1 <= len(raw_patches) <= 8:
        raise SkillError("repair.patches must contain 1-8 items")
    patches: list[tuple[int, str, str]] = []
    for index, raw_patch in enumerate(raw_patches):
        if not isinstance(raw_patch, dict):
            raise SkillError(f"repair.patches[{index}] must be an object")
        order = require_int(
            raw_patch.get("order"),
            f"repair.patches[{index}].order",
            minimum=1,
            maximum=len(state["segments"]),
        )
        segment = next((item for item in state["segments"] if item["order"] == order), None)
        if segment is None or segment["status"] != "completed":
            raise SkillError(f"Cannot patch incomplete segment {order}")
        if segment.get("human_edited"):
            raise SkillError(
                f"Segment {order} is human-edited and cannot be overwritten by automatic repair"
            )
        content = require_text(
            raw_patch.get("content"), f"repair.patches[{index}].content", minimum=200
        )
        continuity = raw_patch.get("continuity_summary")
        if continuity is None:
            continuity = segment["continuity_summary"]
        else:
            continuity = require_text(
                continuity, f"repair.patches[{index}].continuity_summary", minimum=10
            )
        patches.append((order, content, continuity))

    patched_orders = {order for order, _, _ in patches}
    critical_orders = {
        order
        for issue in audit["issues"]
        if issue["severity"] == "critical"
        for order in issue["affected_segment_orders"]
    }
    missing_critical = sorted(critical_orders - patched_orders)
    if missing_critical:
        raise SkillError(
            f"Repair must address all critical issue segments; missing: {missing_critical}"
        )
    if any(not issue["affected_segment_orders"] for issue in audit["issues"] if issue["severity"] == "critical"):
        raise SkillError(
            "A critical issue has no affected segment and cannot be verified by a segment patch"
        )

    for order, content, continuity in patches:
        segment = next(item for item in state["segments"] if item["order"] == order)
        segment["content"] = content
        segment["continuity_summary"] = continuity
        segment["version"] = int(segment.get("version", 0)) + 1
        atomic_write(root / "segments" / f"{order:02d}.md", content.strip() + "\n")

    residual = raw.get("residual_quality_debt", [])
    if not isinstance(residual, list) or len(residual) > 20:
        raise SkillError("residual_quality_debt must be a list with at most 20 items")
    debt = [
        require_text(item, f"residual_quality_debt[{index}]", minimum=4)
        for index, item in enumerate(residual)
    ]
    state["repair_attempted"] = True
    state["quality_debt"] = debt
    state["repair"] = {
        "patched_orders": sorted(patched_orders),
        "residual_quality_debt": debt,
        "applied_at": now_iso(),
    }
    state["status"] = "repair_applied"
    save_state(root, state)
    render_review(root, state)
    story_chars = build_story(root, state)
    return {
        "status": "ok",
        "patched_orders": sorted(patched_orders),
        "story_char_count": story_chars,
        "residual_quality_debt": debt,
    }


def command_finalize(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    ensure_complete_segments(state)
    audit = state.get("audit")
    if not audit:
        raise SkillError("Run the whole-story audit before finalizing")
    if audit["decision"] == "replan_required":
        raise SkillError("The current audit requires replanning")
    if audit["decision"] == "patchable" and not state.get("repair_attempted"):
        raise SkillError("The patchable audit requires the one permitted repair before delivery")
    story_chars = total_chars(state)
    if story_chars < round(state["target_word_count"] * MIN_ACCEPT_RATIO):
        raise SkillError("The story remains below 70% of the target length")
    state["status"] = "completed"
    save_state(root, state)
    final_chars = build_story(root, state)
    return {
        "status": "ok",
        "title": state["title"],
        "story_path": str(root / "story.md"),
        "story_char_count": final_chars,
        "target_word_count": state["target_word_count"],
        "quality_debt": state.get("quality_debt", []),
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = load_state(root)
    segments = state.get("segments", [])
    return {
        "status": "ok",
        "workflow_status": state["status"],
        "title": state.get("title", ""),
        "target_word_count": state["target_word_count"],
        "story_char_count": total_chars(state),
        "segments": [
            {
                "order": segment["order"],
                "status": segment["status"],
                "char_count": char_count(segment.get("content", "")),
                "human_edited": segment.get("human_edited", False),
            }
            for segment in segments
        ],
        "audit_decision": (state.get("audit") or {}).get("decision"),
        "repair_attempted": state.get("repair_attempted", False),
        "quality_debt": state.get("quality_debt", []),
    }


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = check_state(root, load_state(root))
    return {
        "status": "ok",
        "message": "State is structurally valid",
        "workflow_status": state["status"],
        "segment_count": len(state.get("segments", [])),
        "story_char_count": total_chars(state),
    }


def command_build(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).expanduser().resolve()
    state = check_state(root, load_state(root))
    story_chars = build_story(root, state)
    return {"status": "ok", "story_path": str(root / "story.md"), "story_char_count": story_chars}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage a resumable ai-novel-short-story project."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a new short-story project")
    init_parser.add_argument("root", help="Project directory")
    init_parser.add_argument("--idea", required=True, help="The user's original idea")
    init_parser.add_argument("--target", required=True, type=int, help="Target non-whitespace characters")
    init_parser.add_argument("--platform", default="通用中文商业网文", help="Target platform or writing profile")
    init_parser.set_defaults(handler=command_init)

    directions_parser = subparsers.add_parser("set-directions", help="Save three proposed directions")
    directions_parser.add_argument("root")
    directions_parser.add_argument("--input", required=True, help="Directions JSON file")
    directions_parser.set_defaults(handler=command_set_directions)

    choose_parser = subparsers.add_parser("choose-direction", help="Select one direction")
    choose_parser.add_argument("root")
    choose_parser.add_argument("--id", required=True)
    choose_parser.set_defaults(handler=command_choose_direction)

    plan_parser = subparsers.add_parser("set-plan", help="Validate and save the segment plan")
    plan_parser.add_argument("root")
    plan_parser.add_argument("--input", required=True, help="Plan JSON file")
    plan_parser.set_defaults(handler=command_set_plan)

    save_parser = subparsers.add_parser("save-segment", help="Save the next drafted segment")
    save_parser.add_argument("root")
    save_parser.add_argument("--order", required=True, type=int)
    save_parser.add_argument("--input", required=True, help="Segment JSON file")
    save_parser.set_defaults(handler=command_save_segment)

    edit_parser = subparsers.add_parser("edit-segment", help="Apply a user-directed segment edit")
    edit_parser.add_argument("root")
    edit_parser.add_argument("--order", required=True, type=int)
    edit_parser.add_argument("--input", required=True, help="Segment JSON file")
    edit_parser.add_argument("--human", action="store_true", required=True)
    edit_parser.add_argument(
        "--replace-human",
        action="store_true",
        help="Allow replacing an already human-edited segment after explicit consent",
    )
    edit_parser.set_defaults(handler=command_edit_segment)

    audit_parser = subparsers.add_parser("audit", help="Save the single whole-story audit")
    audit_parser.add_argument("root")
    audit_parser.add_argument("--input", required=True, help="Audit JSON file")
    audit_parser.set_defaults(handler=command_audit)

    repair_parser = subparsers.add_parser("repair", help="Apply the one permitted repair pass")
    repair_parser.add_argument("root")
    repair_parser.add_argument("--input", required=True, help="Repair JSON file")
    repair_parser.set_defaults(handler=command_repair)

    finalize_parser = subparsers.add_parser("finalize", help="Validate completion and build story.md")
    finalize_parser.add_argument("root")
    finalize_parser.set_defaults(handler=command_finalize)

    status_parser = subparsers.add_parser("status", help="Show workflow and segment status")
    status_parser.add_argument("root")
    status_parser.set_defaults(handler=command_status)

    validate_parser = subparsers.add_parser("validate", help="Validate persisted workflow state")
    validate_parser.add_argument("root")
    validate_parser.set_defaults(handler=command_validate)

    build_parser_cmd = subparsers.add_parser("build", help="Rebuild continuous story.md from segments")
    build_parser_cmd.add_argument("root")
    build_parser_cmd.set_defaults(handler=command_build)

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
