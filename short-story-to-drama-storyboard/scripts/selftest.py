#!/usr/bin/env python3
"""Integration checks for drama_state.py using temporary projects."""

from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

import drama_state as state


SOURCE = "# 她请我拍最后一张\n\n" + (
    "婚礼开始前，摄影师林夏认出新娘苏遥正是三年前盗用她作品的人。"
    "苏遥把一张旧存储卡塞进她手里，要求她立刻删除全部旧照片。"
    "林夏发现盗图账号的登录设备又出现在婚礼现场。\n\n"
) * 25


def write_json(root: Path, name: str, value: dict) -> str:
    path = root / name
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return str(path)


def adaptation() -> dict:
    return {
        "title": "她请我拍最后一张",
        "genre": "都市情感悬疑",
        "target_audience": "偏好强反转和关系救赎的竖屏短剧用户",
        "logline": "摄影师在婚礼现场发现旧日仇人正被同一个操纵者控制。",
        "positioning": "婚礼倒计时中的证据反击与关系反转",
        "main_pleasure_line": "旧怨被重新解释，两位女性从敌对走向联合反击",
        "adaptation_strategy": "压缩三年前往事，把证据冲突集中到婚礼倒计时中。",
        "must_keep": [
            "林夏因三年前的盗图事件失去工作",
            "苏遥的账号曾发布林夏的作品",
            "原始文件包含不可伪造的拍摄时间",
        ],
        "allowed_changes": ["合并次要同学角色"],
        "deviations": ["新增婚礼控制室作为证据恢复空间"],
        "characters": [
            {
                "name": "林夏",
                "role": "婚礼摄影师、主角",
                "motivation": "查清旧案并决定是否公开真相",
                "visual_anchor": "29岁，黑色短发，深灰工装摄影马甲，右手戴旧快门手链",
            },
            {
                "name": "苏遥",
                "role": "新娘",
                "motivation": "摆脱幕后控制并保护家人",
                "visual_anchor": "28岁，肩长发，白色极简婚纱，左手握旧存储卡",
            },
        ],
        "paywall_plan": None,
    }


def episodes() -> dict:
    return {
        "episodes": [
            {
                "order": 1,
                "title": "删掉三年前的照片",
                "hook_opening": "新娘把存储卡塞给摄影师，要求她立刻删除旧照片。",
                "hook_type": "危机请求",
                "conflict": "摄影师认出新娘是旧案当事人，却不知道她为何恐惧。",
                "cliffhanger": "存储卡里出现一张摄影师从未拍摄过的现场照片。",
                "emotion_net": -2,
                "source_beats": ["婚礼重逢", "删除请求"],
                "target_duration_sec": 90,
                "is_paywall": False,
            },
            {
                "order": 2,
                "title": "不属于我的照片",
                "hook_opening": "陌生照片开始倒计时自动删除。",
                "hook_type": "倒计时",
                "conflict": "摄影师必须在设备被收走前恢复云端记录。",
                "cliffhanger": "恢复文件的设备编号指向新郎家族公司。",
                "emotion_net": -1,
                "source_beats": ["设备被收", "设备编号"],
                "target_duration_sec": 90,
                "is_paywall": False,
            },
        ]
    }


def script(order: int) -> dict:
    return {
        "content": (
            f"场景 1｜婚礼宴会厅｜日\n\n"
            f"动作：苏遥穿过宾客，把存储卡塞进林夏掌心。\n\n"
            f"苏遥：全部删掉。现在。\n\n"
            f"林夏：你凭什么命令我？\n\n"
            f"动作：苏遥看见二楼有人举着手机，后退半步。\n\n"
            f"场景 2｜控制室｜日\n\n"
            f"动作：林夏插入存储卡，陌生照片开始倒计时。\n\n"
            f"林夏：这不是我拍的照片。"
        ),
        "duration_sec": 90,
        "scene_count": 2,
        "opening_3s": "新娘强行把存储卡塞给摄影师并要求删除旧照片。",
        "ending_cliffhanger": "照片倒计时结束后会自动上传并暴露旧案证据。",
        "newly_introduced_facts": [f"第{order}集的证据正在被远程控制"],
        "episode_summary": "林夏重新卷入三年前的旧案，并发现证据正被远程操控。",
    }


def quality(status_value: str = "approved") -> dict:
    flags = (
        [
            {
                "severity": "high",
                "code": "middle_exposition",
                "evidence": "控制室内的说明重复了已知信息。",
                "suggestion": "把说明改成插入存储卡后立即出现的行动结果。",
            }
        ]
        if status_value == "repairable"
        else []
    )
    return {
        "status": status_value,
        "score": {
            "hook": 88,
            "density": 82,
            "paywall": 70,
            "emotion": 84,
            "duration": 90,
            "consistency": 92,
            "overall": 86,
        },
        "flags": flags,
        "repair_plan": (
            {"mode": "patch", "instruction": "把重复说明改为动作和证据变化。"}
            if flags
            else None
        ),
    }


def storyboard() -> dict:
    return {
        "summary": "婚礼现场交卡与远程照片倒计时，建立旧案主线。",
        "shots": [
            {
                "order": 1,
                "shot_size": "中近景",
                "camera_move": "手持跟拍",
                "duration_sec": 4,
                "location": "婚礼宴会厅",
                "action": "苏遥穿过人群，把存储卡塞进林夏掌心。",
                "dialogue": "苏遥：全部删掉。现在。",
                "character_refs": ["苏遥", "林夏"],
                "visual_prompt": "9:16竖屏婚礼现场，新娘把银色存储卡压进摄影师掌心",
            },
            {
                "order": 2,
                "shot_size": "特写",
                "camera_move": "快速推近",
                "duration_sec": 3,
                "location": "控制室",
                "action": "林夏盯着屏幕上自动倒计时的陌生照片。",
                "dialogue": "林夏：这不是我拍的。",
                "character_refs": ["林夏"],
                "visual_prompt": "9:16竖屏，摄影师特写，屏幕冷光照亮她震惊的表情",
            },
        ],
    }


def create_project(temp_root: Path, name: str = "project", episode_count: int = 2) -> Path:
    root = temp_root / name
    source = root / "story.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(SOURCE, encoding="utf-8")
    drama = root / "drama"
    state.command_init(
        Namespace(
            root=str(drama),
            source=str(source),
            episodes=episode_count,
            episode_seconds=90,
            aspect_ratio="9:16",
            title=None,
        )
    )
    return drama


def prepare_adaptation_and_outline(root: Path, episode_count: int = 2) -> None:
    adaptation_path = write_json(root, "adaptation-input.json", adaptation())
    state.command_save_adaptation(Namespace(root=str(root), input=adaptation_path))
    episode_value = episodes()
    episode_value["episodes"] = episode_value["episodes"][:episode_count]
    episodes_path = write_json(root, "episodes-input.json", episode_value)
    state.command_save_episodes(Namespace(root=str(root), input=episodes_path))


def test_single_episode_flow(temp_root: Path) -> None:
    root = create_project(temp_root, "single", episode_count=1)
    prepare_adaptation_and_outline(root, episode_count=1)
    script_path = write_json(root, "single-script.json", script(1))
    state.command_save_script(Namespace(root=str(root), episode=1, input=script_path))
    quality_path = write_json(root, "single-quality.json", quality())
    state.command_save_quality(Namespace(root=str(root), episode=1, input=quality_path))
    storyboard_path = write_json(root, "single-storyboard.json", storyboard())
    state.command_save_storyboard(
        Namespace(root=str(root), episode=1, input=storyboard_path)
    )
    result = state.command_finalize(Namespace(root=str(root)))
    assert result["episode_count"] == 1
    assert "第 1 集" in (root / "storyboard.md").read_text(encoding="utf-8")
    status = state.command_status(Namespace(root=str(root)))
    assert status["target_episodes"] == 1


def test_complete_flow(temp_root: Path) -> None:
    root = create_project(temp_root, "complete")
    prepare_adaptation_and_outline(root)
    second_script = write_json(root, "script-2.json", script(2))
    try:
        state.command_save_script(Namespace(root=str(root), episode=2, input=second_script))
    except state.SkillError as exc:
        assert "Sequential scripting" in str(exc)
    else:
        raise AssertionError("Out-of-order script should be rejected")

    first_script = write_json(root, "script-1.json", script(1))
    state.command_save_script(Namespace(root=str(root), episode=1, input=first_script))
    storyboard_path = write_json(root, "storyboard-1.json", storyboard())
    try:
        state.command_save_storyboard(
            Namespace(root=str(root), episode=1, input=storyboard_path)
        )
    except state.SkillError as exc:
        assert "current approved" in str(exc)
    else:
        raise AssertionError("Storyboard before quality review should be rejected")

    quality_path = write_json(root, "quality-1.json", quality())
    state.command_save_quality(Namespace(root=str(root), episode=1, input=quality_path))
    state.command_save_storyboard(
        Namespace(root=str(root), episode=1, input=storyboard_path)
    )
    state.command_save_script(Namespace(root=str(root), episode=2, input=second_script))
    quality_path_2 = write_json(root, "quality-2.json", quality())
    state.command_save_quality(Namespace(root=str(root), episode=2, input=quality_path_2))
    state.command_save_storyboard(
        Namespace(root=str(root), episode=2, input=storyboard_path)
    )
    result = state.command_finalize(Namespace(root=str(root)))
    assert result["episode_count"] == 2
    output = (root / "storyboard.md").read_text(encoding="utf-8")
    assert "第 1 集" in output and "镜头 1" in output
    assert "source_sha256" not in output
    state.command_validate(Namespace(root=str(root)))


def test_single_repair_and_source_change(temp_root: Path) -> None:
    root = create_project(temp_root, "repair")
    prepare_adaptation_and_outline(root)
    first_script = write_json(root, "script-1.json", script(1))
    state.command_save_script(Namespace(root=str(root), episode=1, input=first_script))
    repair_quality = write_json(root, "quality-repair.json", quality("repairable"))
    state.command_save_quality(
        Namespace(root=str(root), episode=1, input=repair_quality)
    )
    repaired_path = write_json(root, "script-repaired.json", script(1))
    state.command_repair_script(
        Namespace(root=str(root), episode=1, input=repaired_path)
    )
    try:
        state.command_repair_script(
            Namespace(root=str(root), episode=1, input=repaired_path)
        )
    except state.SkillError as exc:
        assert "already been used" in str(exc)
    else:
        raise AssertionError("A second script repair should be rejected")

    source_path = Path(state.load_state(root)["source"]["path"])
    source_path.write_text(SOURCE + "\n新增的一行。\n", encoding="utf-8")
    changed = state.command_check_source(Namespace(root=str(root)))
    assert changed["source_changed"] is True


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="short-story-drama-test-") as temp:
        root = Path(temp)
        test_single_episode_flow(root)
        test_complete_flow(root)
        test_single_repair_and_source_change(root)
    print("selftest: ok")


if __name__ == "__main__":
    main()
