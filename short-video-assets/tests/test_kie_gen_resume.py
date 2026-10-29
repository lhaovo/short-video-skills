import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("kie_gen", ROOT / "scripts" / "kie_gen.py")
kie_gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kie_gen)


def success(task_id: str, url: str) -> dict:
    return {
        "code": 200,
        "data": {
            "taskId": task_id,
            "state": "success",
            "resultJson": '{"resultUrls":["' + url + '"]}',
        },
    }


class KieGenResumeTests(unittest.TestCase):
    def test_task_id_is_persisted_before_download_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "01-资产图" / "PR-01_产品主图_v1.png"
            ledger = root / "00-生图任务"
            with (
                mock.patch.object(kie_gen, "create_task", return_value="task-1") as create,
                mock.patch.object(
                    kie_gen,
                    "wait_for",
                    return_value=success("task-1", "https://example.test/image.png"),
                ),
                mock.patch.object(
                    kie_gen,
                    "download_with_retry",
                    side_effect=kie_gen.DownloadError("SSL handshake timeout"),
                ),
            ):
                with self.assertRaises(kie_gen.DownloadError):
                    kie_gen.submit_or_resume(
                        key="key",
                        prompt="test prompt",
                        ratio="9:16",
                        resolution="1K",
                        source_refs=[],
                        callback=None,
                        out=out,
                        ledger_dir=ledger,
                        interval=1,
                        timeout=5,
                    )

            fingerprint = kie_gen.request_fingerprint("test prompt", "9:16", "1K", [])
            record_path = kie_gen.task_record_path(ledger, out, fingerprint)
            record = kie_gen.load_record(record_path)
            self.assertEqual(create.call_count, 1)
            self.assertEqual(record["task_id"], "task-1")
            self.assertEqual(record["state"], kie_gen.DOWNLOAD_PENDING)
            self.assertIn("SSL", record["last_error"])

    def test_retry_resumes_same_task_without_new_submission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "01-资产图" / "PR-01_产品主图_v1.png"
            ledger = root / "00-生图任务"
            fingerprint = kie_gen.request_fingerprint("test prompt", "9:16", "1K", [])
            record_path = kie_gen.task_record_path(ledger, out, fingerprint)
            kie_gen.write_record(
                record_path,
                {
                    "schema_version": 1,
                    "asset_id": "PR-01",
                    "output": str(out),
                    "fingerprint": fingerprint,
                    "task_id": "task-1",
                    "state": kie_gen.DOWNLOAD_PENDING,
                    "last_error": "SSL handshake timeout",
                    "history": [],
                    "created_at": kie_gen.utc_now(),
                },
            )

            def fake_download(*_args, **_kwargs):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
                return out.stat().st_size

            with (
                mock.patch.object(kie_gen, "create_task") as create,
                mock.patch.object(
                    kie_gen,
                    "wait_for",
                    return_value=success("task-1", "https://example.test/fresh.png"),
                ),
                mock.patch.object(kie_gen, "download_with_retry", side_effect=fake_download),
            ):
                result = kie_gen.submit_or_resume(
                    key="key",
                    prompt="test prompt",
                    ratio="9:16",
                    resolution="1K",
                    source_refs=[],
                    callback=None,
                    out=out,
                    ledger_dir=ledger,
                    interval=1,
                    timeout=5,
                )

            create.assert_not_called()
            self.assertEqual(result["taskId"], "task-1")
            self.assertEqual(result["state"], kie_gen.DOWNLOADED_PENDING_QC)

    def test_download_retry_queries_original_task_for_fresh_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "image.png"
            attempts = [
                kie_gen.DownloadError("connection reset"),
                out.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
                or out.stat().st_size,
            ]
            with (
                mock.patch.object(kie_gen, "download_once", side_effect=attempts),
                mock.patch.object(
                    kie_gen,
                    "query_task",
                    return_value=success("task-1", "https://example.test/fresh.png"),
                ) as query,
            ):
                size = kie_gen.download_with_retry(
                    "key",
                    "task-1",
                    "https://example.test/expired.png",
                    out,
                )
            self.assertGreater(size, 0)
            query.assert_called_once()

    def test_failed_api_task_is_not_resubmitted_automatically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "01-资产图" / "PR-01_产品主图_v1.png"
            ledger = root / "00-生图任务"
            fingerprint = kie_gen.request_fingerprint("test prompt", "9:16", "1K", [])
            record_path = kie_gen.task_record_path(ledger, out, fingerprint)
            kie_gen.write_record(
                record_path,
                {
                    "schema_version": 1,
                    "asset_id": "PR-01",
                    "output": str(out),
                    "fingerprint": fingerprint,
                    "task_id": "failed-task",
                    "state": kie_gen.TASK_FAILED,
                    "last_error": "provider failure",
                    "history": [],
                    "created_at": kie_gen.utc_now(),
                },
            )

            with mock.patch.object(kie_gen, "create_task") as create:
                with self.assertRaises(kie_gen.TaskFailedError):
                    kie_gen.submit_or_resume(
                        key="key",
                        prompt="test prompt",
                        ratio="9:16",
                        resolution="1K",
                        source_refs=[],
                        callback=None,
                        out=out,
                        ledger_dir=ledger,
                        interval=1,
                        timeout=5,
                    )
            create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
