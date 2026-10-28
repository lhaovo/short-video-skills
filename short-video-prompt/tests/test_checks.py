import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen_check = load_module("check_gen_list", ROOT / "scripts" / "check_gen_list.py")


class FieldTableTests(unittest.TestCase):
    def test_empty_table_fails_every_field(self):
        table = "| 画面字段 | 本段描述 |\n|---|---|\n" + "\n".join(
            f"| {field} |  |" for field in gen_check.TABLE_FIELDS
        )
        values = gen_check.find_field_table(table)
        self.assertEqual(
            [field for field in gen_check.TABLE_FIELDS if gen_check.is_blank(values[field], field)],
            list(gen_check.TABLE_FIELDS),
        )

    def test_template_placeholders_are_blank(self):
        self.assertTrue(gen_check.is_blank("{{具体动作}}", "动作"))
        self.assertTrue(gen_check.is_blank("{{无；写原因}}", "依赖/可见事实"))

    def test_prose_keywords_do_not_substitute_for_table(self):
        body = "主体、状态、动作、环境、光线、景别、机位/角度和运镜均已描述。"
        self.assertIsNone(gen_check.find_field_table(body))

    def test_no_is_only_valid_for_dependency_fact(self):
        self.assertFalse(gen_check.is_blank("无", "依赖/可见事实"))
        self.assertTrue(gen_check.is_blank("无", "主体"))

    def test_drama_storyboard_json_supplies_target_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "01.json"
            path.write_text(
                json.dumps(
                    {
                        "summary": "单集测试",
                        "shots": [
                            {"order": 1, "duration_sec": 4},
                            {"order": 2, "duration_sec": 6},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            self.assertEqual(gen_check.parse_target_from_storyboard(path), 10.0)

    def test_readable_drama_storyboard_supplies_target_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "storyboard.md"
            path.write_text(
                "### 镜头 1｜中景｜4 秒｜客厅\n\n"
                "### 镜头 2｜特写｜3 秒｜客厅\n",
                encoding="utf-8",
            )
            self.assertEqual(gen_check.parse_target_from_storyboard(path), 7.0)


if __name__ == "__main__":
    unittest.main()
