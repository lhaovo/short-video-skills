import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_plan.py"
spec = importlib.util.spec_from_file_location("check_plan", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample(dependency="镜 1：已建立队列"):
    return f"""# 策划案
> 目标时长：4s
## 四、分镜表
| 镜号 | 时长(s) | 这一镜讲什么 | 口播 | 屏幕文字 | 本镜功能 |
|---|---:|---|---|---|---|
| 1 | 2 | 排队的顾客 | 无 | 无 | 建立场景 |
| 2 | 2 | 人物往前走 | 让一让 | 无 | 推动冲突 |

### 镜 1
- 观众认知：这里有人排队
- 前置依赖：无
- 关键可见事实：队伍在店门口
- 时长意图：用脚步和环境音铺陈场景

### 镜 2
- 观众认知：有人插队
- 前置依赖：{dependency}
- 关键可见事实：人物站到队伍前端
- 时长意图：台词与动作同时完成

## 五、自检结果
"""


class PlanTests(unittest.TestCase):
    def test_valid_short_table(self):
        result = module.check(sample())
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["shots"], 2)

    def test_future_dependency_fails(self):
        result = module.check(sample("镜 3：尚未出现"))
        self.assertFalse(result["ok"])
        self.assertTrue(any("未早于本镜" in error for error in result["errors"]))

    def test_placeholder_fails(self):
        result = module.check(sample().replace("队伍在店门口", "{{可见事实}}"))
        self.assertFalse(result["ok"])

    def test_old_case_is_not_mistaken_for_short_table(self):
        case = Path(__file__).resolve().parents[2] / "outputs" / "2026-10-22-丁克大脚丫治插队恶霸" / "01-策划案.md"
        if case.is_file():
            result = module.check(case.read_text(encoding="utf-8"))
            self.assertEqual(result["format"], "legacy-5")
            self.assertFalse(result["ok"])
            self.assertEqual(result["shots"], 32)
            self.assertEqual(len(result["errors"]), 2)

    def test_not_applicable_with_reason_is_valid(self):
        result = module.check(sample().replace("镜 1：已建立队列", "不适用：本镜独立成立"))
        self.assertTrue(result["ok"], result["errors"])

    def test_not_applicable_without_reason_fails(self):
        result = module.check(sample().replace("镜 1：已建立队列", "不适用"))
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
