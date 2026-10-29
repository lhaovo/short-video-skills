import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_asset_contact_sheet",
    ROOT / "scripts" / "build_asset_contact_sheet.py",
)
sheet = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sheet
SPEC.loader.exec_module(sheet)


def write_png(path: Path, color: tuple[int, int, int, int], size=(80, 120)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ContactSheetTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        assets = root / "04-素材" / "01-资产图"
        assets.mkdir(parents=True)
        (root / "04-素材" / "00-工单.md").write_text(
            "\n".join(
                [
                    "| 编号 | 用途 | 级别 | 采用版本 | 状态 |",
                    "|---|---|---|---|---|",
                    "| PR-01 | 产品包装 | 锚点 | v2 | 已有 |",
                    "| SC-01 | 商业街 | 锚点 | v1 | 已有 |",
                    "| CH-01 | 恶霸 | 锚点 | v2 | 已有 |",
                    "| CH-02 | 少年 | 派生 | v1 | 已有 |",
                    "| SP-01 | 道具车 | 一次性 | v1 | 已有 |",
                ]
            ),
            encoding="utf-8",
        )
        (root / "02-资产清单.md").write_text(
            "\n".join(
                [
                    "# 资产清单 · 接触印样测试",
                    "",
                    "| 编号 | 类型 | 用途 | 来源 | 被哪些段引用 | 状态 |",
                    "|---|---|---|---|---|---|",
                    "| PR-01 | 产品 | 产品包装 | AI | S01 | 已有（定版 v2） |",
                    "| SC-01 | 场景 | 商业街 | AI | S01 | 已有（定版 v1） |",
                    "| CH-01 | 人物 | 恶霸 | AI | S01 | 已有（定版 v2） |",
                    "| CH-02 | 人物 | 少年 | AI | S02 | 已有（定版 v1） |",
                    "| SP-01 | 道具 | 道具车 | AI | S02 | 已有（定版 v1） |",
                    "| SP-02 | 道具 | 后期叠字 | 后期 | S03 | 待叠字 |",
                ]
            ),
            encoding="utf-8",
        )
        write_png(assets / "PR-01_产品包装_v1.png", (255, 0, 0, 255))
        write_png(assets / "PR-01_产品包装_v2.png", (220, 180, 60, 255))
        write_png(assets / "SC-01_商业街_v1.png", (40, 90, 170, 255), size=(120, 80))
        write_png(assets / "CH-01_恶霸_v2.png", (0, 0, 0, 0), size=(90, 140))
        write_png(assets / "CH-02_少年_v1.png", (20, 120, 70, 255))
        write_png(assets / "SP-01_道具车_v1.png", (80, 80, 80, 255))
        return assets

    def test_dynamic_count_order_and_source_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = self.make_project(root)
            before = {
                path.name: digest(path)
                for path in assets_dir.iterdir()
                if path.is_file()
            }
            output = root / "04-素材" / "00-审阅" / "overview.jpg"
            result = sheet.build(
                Namespace(
                    project=str(root),
                    expected_count=5,
                    columns=2,
                    canvas=(800, 1400),
                    quality=92,
                    output=str(output),
                    overwrite=False,
                    font=None,
                )
            )
            self.assertEqual(result["count"], 5)
            self.assertEqual(
                [item["asset_id"] for item in result["assets"]],
                ["PR-01", "SC-01", "CH-01", "CH-02", "SP-01"],
            )
            self.assertEqual(result["assets"][0]["version"], "v2")
            self.assertEqual(result["assets"][1]["version"], "v1")
            self.assertTrue(output.is_file())
            with Image.open(output) as image:
                self.assertEqual(image.size, (800, 1400))
                self.assertEqual(image.format, "JPEG")
            metadata = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["count"], 5)
            after = {
                path.name: digest(path)
                for path in assets_dir.iterdir()
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_transparent_asset_is_composited_on_white(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = self.make_project(root)
            warning: list[str] = []
            item = {
                "asset_id": "CH-01",
                "category": "CH",
                "kind": "人物",
                "purpose": "恶霸",
                "source": "AI",
                "status": "已有",
                "version": "v2",
            }
            asset = sheet.load_asset(assets_dir, item, warning)
            image = sheet.image_for_asset(asset)
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_expected_count_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            with self.assertRaises(sheet.SheetError):
                sheet.build(
                    Namespace(
                        project=str(root),
                        expected_count=15,
                        columns=4,
                        canvas=(1580, 2756),
                        quality=92,
                        output=None,
                        overwrite=False,
                        font=None,
                    )
                )

    def test_fifteen_assets_fit_fixed_four_by_four_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = root / "04-素材" / "01-资产图"
            assets_dir.mkdir(parents=True)
            ids = ["PR-01", "SC-01"] + [f"CH-{i:02d}" for i in range(1, 11)] + [
                f"SP-{i:02d}" for i in range(1, 4)
            ]
            list_rows = [
                "# 资产清单 · 十五项",
                "",
                "| 编号 | 类型 | 用途 | 来源 | 被哪些段引用 | 状态 |",
                "|---|---|---|---|---|---|",
            ]
            order_rows = [
                "| 编号 | 用途 | 级别 | 采用版本 | 状态 |",
                "|---|---|---|---|---|",
            ]
            for index, asset_id in enumerate(ids, 1):
                kind = "产品" if asset_id.startswith("PR") else (
                    "场景" if asset_id.startswith("SC") else (
                        "人物" if asset_id.startswith("CH") else "道具"
                    )
                )
                list_rows.append(
                    f"| {asset_id} | {kind} | 测试用途 | AI | S01 | 已有（定版 v1） |"
                )
                order_rows.append(f"| {asset_id} | 测试用途 | 锚点 | v1 | 已有 |")
                write_png(
                    assets_dir / f"{asset_id}_测试用途_v1.png",
                    ((index * 17) % 255, (index * 29) % 255, (index * 41) % 255, 255),
                    size=(40, 60),
                )
            (root / "02-资产清单.md").write_text("\n".join(list_rows), encoding="utf-8")
            (root / "04-素材" / "00-工单.md").write_text(
                "\n".join(order_rows),
                encoding="utf-8",
            )
            output = root / "04-素材" / "00-审阅" / "overview.jpg"
            result = sheet.build(
                Namespace(
                    project=str(root),
                    expected_count=15,
                    columns=4,
                    canvas=(1580, 2756),
                    quality=92,
                    output=str(output),
                    overwrite=False,
                    font=None,
                )
            )
            self.assertEqual(result["count"], 15)
            self.assertEqual(result["rows"], 4)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1580, 2756))

    def test_exif_orientation_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets_dir = root / "04-素材" / "01-资产图"
            assets_dir.mkdir(parents=True)
            image = Image.new("RGB", (40, 80), "#336699")
            exif = Image.Exif()
            exif[274] = 6
            image.save(assets_dir / "CH-01_测试_v1.jpg", exif=exif)
            warning: list[str] = []
            item = {
                "asset_id": "CH-01",
                "category": "CH",
                "kind": "人物",
                "purpose": "测试",
                "source": "AI",
                "status": "已有",
                "version": "v1",
            }
            asset = sheet.load_asset(assets_dir, item, warning)
            self.assertEqual(asset.exif_orientation, 6)
            self.assertEqual((asset.original_width, asset.original_height), (40, 80))
            self.assertEqual((asset.display_width, asset.display_height), (80, 40))


if __name__ == "__main__":
    unittest.main()
