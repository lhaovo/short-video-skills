#!/usr/bin/env python3
"""Integration checks for story_state.py using temporary projects."""

from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

import story_state as state


IDEA = "一个被赶出公司的女财务回到旧公司，在董事表决前证明自己遭人伪造证据。"
TARGET = 3_000
PROSE = "她把原件放在桌上，会议室里的争论立刻停了。对方翻开复印页，时间戳与门禁记录对不上。\n\n" * 70


def write_json(root: Path, name: str, value: dict) -> str:
    path = root / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return str(path)


def directions() -> dict:
    return {
        "understanding": "用户想写一个有证据链、克制的职场反击短篇。",
        "recommendation_reason": "单一冲突可以在一场表决前后完成升级和兑现，适合短篇。",
        "platform": "知乎短故事",
        "platform_reason": "紧凑的职场对峙适合第一人称高压叙事。",
        "directions": [
            {
                "id": "ledger",
                "title": "最后一本账",
                "premise": "女财务回到旧公司，在表决前用原始账本推翻伪造指控。",
                "core_experience": "克制的证据反击与公开翻盘。",
                "protagonist": "被赶走三年的女财务林昭。",
                "central_conflict": "她必须在证据被销毁前阻止表决。",
                "ending_promise": "她靠自己保留的证据洗清指控并阻止错误并购。",
                "style_keywords": ["证据链推进", "克制的压迫感", "公开对峙"],
            },
            {
                "id": "key",
                "title": "没有名字的继承人",
                "premise": "被忽视的女儿只继承一把钥匙，必须在房子出售前找到它打开的房间。",
                "core_experience": "家庭谜团最终落到亲人迟来的保护。",
                "protagonist": "长期被忽视的女儿苏晚。",
                "central_conflict": "兄妹阻挠她寻找房间，而买家不断提前交割。",
                "ending_promise": "钥匙揭开父亲刻意留下的保护，她选择自己的未来。",
                "style_keywords": ["物件线索", "家庭悬念", "克制亲情"],
            },
            {
                "id": "nine-minutes",
                "title": "开盘前九分钟",
                "premise": "初级风控分析员发现九分钟后的市场崩溃已经被交易系统提前录制。",
                "core_experience": "实时倒计时中的技术证据攻防。",
                "protagonist": "即将替失效模型背责的初级风控分析员陈雨。",
                "central_conflict": "她要在所有人把警报当成测试时保住被篡改的日志。",
                "ending_promise": "她证明崩溃是人为安排，并迫使系统所有者承认欺诈。",
                "style_keywords": ["实时倒计时", "技术证据", "密闭空间"],
            },
        ],
    }


def plan() -> dict:
    def segment(order: int, title: str) -> dict:
        return {
            "order": order,
            "purpose": title,
            "target_word_count": 1_000,
            "opening_state": "林昭刚刚回到公司，并购表决即将开始。",
            "opening_hook": "财务总监看到她手中的原始账本后突然中止会议。",
            "immediate_goal": "在文件销毁前完成证据链核对。",
            "progression_beats": [
                "她发现伪造页使用了错误的时间戳。",
                "她拒绝买方提出的私下和解。",
                "她把证据交给独立董事复核。",
            ],
            "turning_point": "门禁记录证明她在伪造页落款时并不在公司。",
            "payoff": "证据链完成，错误指控不攻自破。",
            "closing_pull": "买方代表拿出了另一份未公开的授权书。",
            "closing_state": "表决暂停，新的利益关系暴露。",
        }

    return {
        "title": "最后一本账",
        "target_word_count": TARGET,
        "ending_promise": "林昭靠自己的证据洗清指控，并阻止错误并购。",
        "segments": [
            segment(1, "迫使林昭进入证据争夺。"),
            segment(2, "升级买方与董事会之间的压力。"),
            segment(3, "完成公开反击并收束个人去留。"),
        ],
        "causal_contract": {
            "protagonist_goal": "在表决前证明伪造证据并阻止并购。",
            "central_question": "林昭能否证明自己遭到陷害？",
            "fixed_facts": [
                "林昭三年前被迫离开公司。",
                "原始账本带有完整交接记录。",
                "并购表决会触发旧档案销毁。",
            ],
            "cause_effect_chain": [
                "因为档案将被销毁，林昭必须立即返回公司。",
                "因为门禁记录与伪造页冲突，她获得第一份反证。",
                "因为她拒绝和解，证据最终进入董事会复核。",
            ],
            "setup_payoffs": [
                {
                    "setup": "旧日历保留了当天的出差记录。",
                    "setup_segment_order": 1,
                    "payoff": "出差记录推翻伪造页的时间。",
                    "payoff_segment_order": 2,
                },
                {
                    "setup": "原始账本附带交接清单。",
                    "setup_segment_order": 1,
                    "payoff": "交接清单证明当前账本经过替换。",
                    "payoff_segment_order": 3,
                },
            ],
        },
    }


def init_project(root: Path) -> None:
    state.command_init(
        Namespace(root=str(root), idea=IDEA, target=TARGET, platform="知乎短故事")
    )


def prepare_plan(root: Path) -> None:
    direction_path = write_json(root, "directions-input.json", directions())
    state.command_set_directions(Namespace(root=str(root), input=direction_path))
    state.command_choose_direction(Namespace(root=str(root), id="ledger"))
    plan_path = write_json(root, "plan-input.json", plan())
    state.command_set_plan(Namespace(root=str(root), input=plan_path))


def write_segments(root: Path) -> None:
    for order in (1, 2, 3):
        segment_path = write_json(
            root,
            f"segment-{order}.json",
            {
                "content": PROSE,
                "continuity_summary": f"第{order}片段完成后，证据链继续推进。",
            },
        )
        state.command_save_segment(
            Namespace(root=str(root), order=order, input=segment_path)
        )


def test_direction_count(temp_root: Path) -> None:
    root = temp_root / "direction-count"
    init_project(root)
    value = directions()
    value["directions"] = value["directions"][:2]
    input_path = write_json(root, "two-directions.json", value)
    try:
        state.command_set_directions(Namespace(root=str(root), input=input_path))
    except state.SkillError as exc:
        assert "exactly three" in str(exc)
    else:
        raise AssertionError("An input with two directions should be rejected")


def test_accepted_flow(temp_root: Path) -> None:
    root = temp_root / "accepted"
    init_project(root)
    prepare_plan(root)
    write_segments(root)
    audit_path = write_json(
        root,
        "audit-input.json",
        {"decision": "accepted", "summary": "因果完整，结局明确。", "issues": []},
    )
    state.command_audit(Namespace(root=str(root), input=audit_path))
    result = state.command_finalize(Namespace(root=str(root)))
    assert result["status"] == "ok"
    assert (root / "story.md").read_text(encoding="utf-8").strip()
    assert "## 片段" not in (root / "story.md").read_text(encoding="utf-8")
    state.command_validate(Namespace(root=str(root)))


def test_single_repair_flow(temp_root: Path) -> None:
    root = temp_root / "repair"
    init_project(root)
    prepare_plan(root)
    write_segments(root)
    audit_path = write_json(
        root,
        "audit-input.json",
        {
            "decision": "patchable",
            "summary": "结尾的董事反应还可以落到动作上。",
            "issues": [
                {
                    "code": "weak_final_reaction",
                    "severity": "standard",
                    "description": "结尾解释了结果，没有呈现董事会当下的反应。",
                    "affected_segment_orders": [3],
                    "repair_instruction": "用表决动作和一句对话收束。",
                }
            ],
        },
    )
    state.command_audit(Namespace(root=str(root), input=audit_path))
    repair_path = write_json(
        root,
        "repair-input.json",
        {
            "patches": [
                {
                    "order": 3,
                    "content": PROSE + "表决结果落下时，林昭把原始账本推向会议桌中央。",
                    "continuity_summary": "表决被停止，林昭保有证据并离开公司。",
                }
            ],
            "residual_quality_debt": ["一名次要董事的背景仍较简略。"],
        },
    )
    state.command_repair(Namespace(root=str(root), input=repair_path))
    try:
        state.command_repair(Namespace(root=str(root), input=repair_path))
    except state.SkillError as exc:
        assert "already been applied" in str(exc)
    else:
        raise AssertionError("A second repair should be rejected")
    result = state.command_finalize(Namespace(root=str(root)))
    assert result["status"] == "ok"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ai-novel-short-story-test-") as temp:
        root = Path(temp)
        test_direction_count(root)
        test_accepted_flow(root)
        test_single_repair_flow(root)
    print("selftest: ok")


if __name__ == "__main__":
    main()
