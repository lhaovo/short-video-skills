import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_sequence", ROOT / "scripts" / "check_sequence.py")
sequence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sequence)


class SequenceTests(unittest.TestCase):
    def write_state(self, root: Path, stage: str, gates: dict[str, tuple[str, str]]) -> None:
        (root / "00-流程状态.md").write_text(
            "\n".join(
                [
                    "# 流程状态",
                    "",
                    "| 项 | 内容 |",
                    "|---|---|",
                    f"| 当前阶段 | {stage} |",
                    "",
                    "| 门 | 阶段 | 技术检查 | 门禁状态 | 批准版本与范围 |",
                    "|---|---|---|---|---|",
                    *[
                        f"| {name} | 测试 | 通过 | {status} | {evidence} |"
                        for name, (status, evidence) in gates.items()
                    ],
                ]
            ),
            encoding="utf-8",
        )

    def test_s1a_can_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(root, "S1A", {"G1-A": ("未开始", "")})
            result = sequence.check_stage(root, "S1A")
            self.assertTrue(result["ok"], result)

    def test_unfilled_template_is_not_treated_as_s1a(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "00-流程状态.md").write_text(
                "| 当前阶段 | {{S1A / S1B / S2}} |\n",
                encoding="utf-8",
            )
            result = sequence.check_stage(root, "S1A")
            self.assertFalse(result["ok"])
            self.assertTrue(any("必须明确填写" in error for error in result["errors"]))

    def test_s1b_requires_g1a_and_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(root, "S1A", {"G1-A": ("等待用户确认", "")})
            result = sequence.check_stage(root, "S1B")
            self.assertFalse(result["ok"])
            self.assertTrue(any("G1-A" in error for error in result["errors"]))

            self.write_state(root, "S1A", {"G1-A": ("已批准", "story.md v1")})
            story = root / "01-故事" / "story.md"
            story.parent.mkdir(parents=True)
            story.write_text("完整故事。\n", encoding="utf-8")
            result = sequence.check_stage(root, "S1B")
            self.assertTrue(result["ok"], result)

    def test_cannot_skip_from_s1a_to_s2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(
                root,
                "S1A",
                {
                    "G1-A": ("已批准", "story.md v1"),
                    "G1-B": ("已批准", "storyboard.md v1"),
                },
            )
            result = sequence.check_stage(root, "S2")
            self.assertFalse(result["ok"])
            self.assertTrue(any("禁止跳步" in error for error in result["errors"]))

    def test_current_stage_still_requires_upstream_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(
                root,
                "S2",
                {
                    "G1-A": ("等待用户确认", "story.md v1"),
                    "G1-B": ("未开始", ""),
                },
            )
            result = sequence.check_stage(root, "S2")
            self.assertFalse(result["ok"])
            self.assertTrue(any("G1-A" in error for error in result["errors"]))

    def test_backward_stage_requires_explicit_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(
                root,
                "S3",
                {
                    "G1-A": ("已批准", "story.md v1"),
                    "G1-B": ("已批准", "storyboard.md v1"),
                    "G2": ("已批准", "03-生成清单.md v1"),
                },
            )
            result = sequence.check_stage(root, "S2")
            self.assertFalse(result["ok"])
            self.assertTrue(any("禁止静默回退" in error for error in result["errors"]))

    def test_technical_pass_is_not_user_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(root, "S1A", {"G1-A": ("通过", "story.md v1")})
            result = sequence.check_stage(root, "S1B")
            self.assertFalse(result["ok"])
            self.assertTrue(any("只有「已批准」" in error for error in result["errors"]))

    def test_g3a_can_be_checked_before_paid_video_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(
                root,
                "S3",
                {
                    "G1-A": ("已批准", "story.md v1"),
                    "G1-B": ("已批准", "storyboard.md v1"),
                    "G2": ("已批准", "03-生成清单.md v1"),
                    "G3-A": ("等待用户确认", ""),
                },
            )
            result = sequence.check_gate(root, "G3-A")
            self.assertFalse(result["ok"])

            self.write_state(
                root,
                "S3",
                {
                    "G1-A": ("已批准", "story.md v1"),
                    "G1-B": ("已批准", "storyboard.md v1"),
                    "G2": ("已批准", "03-生成清单.md v1"),
                    "G3-A": ("已批准", "资产定版 v1，允许视频生成"),
                },
            )
            result = sequence.check_gate(root, "G3-A")
            self.assertTrue(result["ok"], result)

    def test_approval_without_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_state(root, "S1A", {"G1-A": ("已批准", "")})
            result = sequence.check_stage(root, "S1B")
            self.assertFalse(result["ok"])
            self.assertTrue(any("缺少批准版本" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
