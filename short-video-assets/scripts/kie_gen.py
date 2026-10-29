#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIE GPT Image 2 生图执行器（资产准备用）。

提交任务后立即持久化 taskId，再轮询、下载到指定路径并原子落盘。
下载失败按原 taskId 重查地址并重试，不重新提交生图任务。
密钥只从环境变量 KIE_API_KEY 读取，不写入文件、不打印。

用法：
    python kie_gen.py generate --prompt "..." --ratio 9:16 --out 04-素材/01-资产图/PR-01_产品主图_v1.png
    python kie_gen.py generate --prompt "..." --ref 锚点.png --ratio 9:16 --out out.png
    python kie_gen.py generate --prompt "..." --dry-run          # 只看 payload，不花钱
    python kie_gen.py batch --tasks tasks.json --out-dir 04-素材/01-资产图
    python kie_gen.py query --task-id xxx
    python kie_gen.py retrieve --task-id xxx --out 04-素材/01-资产图/PR-01_产品主图_v1.png

退出码：0 成功 / 1 参数、网络或任务错误 / 2 批量中有失败项
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://api.kie.ai"
UPLOAD_BASE_URL = "https://kieai.redpandaai.co"
CREATE_PATH = "/api/v1/jobs/createTask"
QUERY_PATH = "/api/v1/jobs/recordInfo"
UPLOAD_PATH = "/api/file-stream-upload"

MODEL_T2I = "gpt-image-2-text-to-image"
MODEL_I2I = "gpt-image-2-image-to-image"

# 默认 1K：竖屏短视频的资产图与首帧最终都会进视频模型，源头分辨率再高也会被
# 重采样，1K 已够用且出图更快更省。只有需要放大裁切时才显式升 2K / 4K。
DEFAULT_RESOLUTION = "1K"
LEDGER_DIR_NAME = "00-生图任务"
DOWNLOAD_RETRIES = 4

# 批量默认 5 路并发。出图主要是等接口返回，线程池足够，不需要改成异步。
# 被限流（429 或返回 code != 200）时把并发降下来再跑。
DEFAULT_CONCURRENCY = 5

SUCCESS_STATES = {"success", "succeed", "succeeded", "completed", "finished"}
FAIL_STATES = {"fail", "failed", "error", "cancelled", "canceled"}
DOWNLOAD_PENDING = "generated_pending_download"
DOWNLOADED_PENDING_QC = "downloaded_pending_qc"
TASK_FAILED = "failed"


# ---------------- 基础请求 ----------------
def api_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("KIE_API_KEY", "")
    if not key:
        print("缺少 KIE_API_KEY。先设置环境变量，或用 --api-key 临时传入。", file=sys.stderr)
        raise SystemExit(1)
    return key


def request_json(method: str, url: str, key: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Authorization": f"Bearer {key}"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise SystemExit(f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"网络错误：{exc}")


def ensure_ok(resp: dict) -> dict:
    if resp.get("code") != 200:
        raise SystemExit("接口返回异常：" + json.dumps(resp, ensure_ascii=False)[:400])
    return resp


# ---------------- 上传参考图 ----------------
def upload_file(key: str, path: Path, upload_path: str = "images/assets") -> str:
    if not path.is_file():
        raise SystemExit(f"参考图不存在：{path}")
    boundary = "----kie-" + uuid.uuid4().hex
    fname = path.name
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])

    field("uploadPath", upload_path)
    field("fileName", fname)
    parts.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
    ])
    parts.append(path.read_bytes())
    parts.extend([b"\r\n", f"--{boundary}--\r\n".encode()])

    req = urllib.request.Request(
        UPLOAD_BASE_URL + UPLOAD_PATH,
        data=b"".join(parts),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"上传失败 HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
    data = payload.get("data") or {}
    url = data.get("downloadUrl") or data.get("fileUrl")
    if not url:
        raise SystemExit("上传成功但没拿到下载地址：" + json.dumps(payload, ensure_ascii=False)[:300])
    return url


# ---------------- 参数校验 ----------------
def validate(ratio: str, resolution: str | None) -> None:
    r = (resolution or "").strip().lower()
    a = ratio.strip().lower()
    if r == "4k" and a == "1:1":
        raise SystemExit("GPT Image 2 不支持把 1:1 转成 4K，换比例或降分辨率。")
    if r and r != "1k" and a == "auto":
        raise SystemExit("比例 auto 时只能 1K，请显式指定比例。")


def build_payload(prompt: str, ratio: str, resolution: str | None, refs: list[str], callback: str | None) -> dict:
    validate(ratio, resolution)
    model = MODEL_I2I if refs else MODEL_T2I
    body: dict = {"model": model, "input": {"prompt": prompt, "aspect_ratio": ratio}}
    if resolution:
        body["input"]["resolution"] = resolution
    if refs:
        body["input"]["input_urls"] = refs
    if callback:
        body["callBackUrl"] = callback
    return body


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_fingerprint(prompt: str, ratio: str, resolution: str | None, refs: list[str]) -> str:
    """Stable fingerprint based on request content, not temporary upload URLs."""
    ref_keys = []
    for ref in refs:
        if str(ref).startswith(("http://", "https://")):
            ref_keys.append(str(ref))
        else:
            path = Path(ref).expanduser().resolve()
            ref_keys.append(f"file:{file_digest(path)}" if path.is_file() else f"pending:{path}")
    payload = {
        "model": MODEL_I2I if refs else MODEL_T2I,
        "prompt": prompt,
        "ratio": ratio,
        "resolution": resolution,
        "refs": ref_keys,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def resolve_refs(
    refs: list[str],
    base_dir: Path | None = None,
    require_exists: bool = True,
) -> list[str]:
    resolved = []
    for ref in refs:
        if str(ref).startswith(("http://", "https://")):
            resolved.append(str(ref))
            continue
        path = Path(ref).expanduser()
        if not path.is_absolute() and base_dir is not None:
            path = base_dir / path
        path = path.resolve()
        if require_exists and not path.is_file():
            raise SystemExit(f"参考图不存在：{path}")
        resolved.append(str(path))
    return resolved


def ledger_dir_for(out_dir: Path, override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return (out_dir.parent / LEDGER_DIR_NAME).resolve()


def task_record_path(ledger_dir: Path, out: Path, fingerprint: str) -> Path:
    safe_stem = out.stem.replace("/", "_").replace("\\", "_")
    output_key = hashlib.sha256(str(out.resolve()).encode("utf-8")).hexdigest()[:8]
    return ledger_dir / f"{safe_stem}__{fingerprint}__{output_key}.json"


def load_record(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find_record_by_task(ledger_dir: Path, task_id: str, out: Path) -> tuple[Path, dict] | None:
    if not ledger_dir.is_dir():
        return None
    for path in ledger_dir.glob("*.json"):
        record = load_record(path)
        if record and record.get("task_id") == task_id:
            return path, record
    fingerprint = "manual-" + hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:12]
    record = {
        "schema_version": 1,
        "asset_id": asset_id_from_output(out),
        "output": str(out),
        "fingerprint": fingerprint,
        "task_id": task_id,
        "state": "submitted",
        "last_error": None,
        "history": [],
        "created_at": utc_now(),
    }
    return task_record_path(ledger_dir, out, fingerprint), record


def write_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record["updated_at"] = utc_now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def update_record(path: Path, record: dict, **changes) -> dict:
    record.update(changes)
    write_record(path, record)
    return record


# ---------------- 任务 ----------------
def create_task(key: str, body: dict) -> str:
    resp = ensure_ok(request_json("POST", BASE_URL + CREATE_PATH, key, body))
    task_id = (resp.get("data") or {}).get("taskId")
    if not task_id:
        raise SystemExit("没拿到 taskId：" + json.dumps(resp, ensure_ascii=False)[:300])
    return task_id


def query_task(key: str, task_id: str) -> dict:
    url = BASE_URL + QUERY_PATH + "?" + urllib.parse.urlencode({"taskId": task_id})
    return ensure_ok(request_json("GET", url, key))


def result_urls(resp: dict) -> list[str]:
    data = resp.get("data") or {}
    raw = data.get("resultJson")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            parsed = {}
        urls = parsed.get("resultUrls")
        if isinstance(urls, list):
            return [str(url) for url in urls]
    for field in ("resultUrls", "result_urls", "urls"):
        urls = data.get(field)
        if isinstance(urls, list):
            return [str(url) for url in urls]
    return []


class TaskFailedError(RuntimeError):
    pass


class TaskPendingError(RuntimeError):
    pass


def wait_for(key: str, task_id: str, interval: int, timeout: int) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            resp = query_task(key, task_id)
        except SystemExit as exc:
            raise TaskPendingError(f"查询原任务暂时失败：{exc}") from exc
        data = resp.get("data") or {}
        state = str(data.get("state", "")).lower()
        if state != last:
            print(f"  状态：{state or '未知'}", file=sys.stderr)
            last = state
        if result_urls(resp):
            return resp
        if state in FAIL_STATES:
            raise TaskFailedError(f"任务失败：{data.get('failMsg') or data.get('failCode') or state}")
        if state in SUCCESS_STATES and not result_urls(resp):
            raise TaskPendingError("任务已成功但暂时没返回图片地址，按原 taskId 重查")
        time.sleep(interval)
    raise TaskPendingError(f"等待超时（{timeout}s）。可用 query --task-id {task_id} 继续查。")


class DownloadError(RuntimeError):
    pass


def download_once(url: str, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=180) as resp, tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
            fh.flush()
            os.fsync(fh.fileno())
    except (urllib.error.URLError, urllib.error.HTTPError, ssl.SSLError,
            ConnectionError, TimeoutError, OSError) as exc:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"{type(exc).__name__}: {exc}") from exc

    size = tmp.stat().st_size
    with tmp.open("rb") as handle:
        head = handle.read(16)
    if size <= 0 or not (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8")
        or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")
    ):
        tmp.unlink(missing_ok=True)
        raise DownloadError("下载内容不是有效图片")
    os.replace(tmp, out)
    return size


def download_with_retry(
    key: str,
    task_id: str,
    initial_url: str,
    out: Path,
    retries: int = DOWNLOAD_RETRIES,
) -> int:
    """Retry only the download. Re-query the original task for a fresh URL."""
    last_error = "未知下载错误"
    for attempt in range(1, retries + 1):
        try:
            if attempt == 1:
                url = initial_url
            else:
                resp = query_task(key, task_id)
                urls = result_urls(resp)
                if not urls:
                    raise DownloadError("任务成功但暂时没有可下载地址")
                url = urls[0]
            return download_once(url, out)
        except (DownloadError, SystemExit, OSError, TimeoutError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(2 ** attempt, 8))
    raise DownloadError(f"连续 {retries} 次下载失败，原 taskId 保留：{task_id}；{last_error}")


def image_file_valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    return (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8")
        or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")
    )


def asset_id_from_output(out: Path) -> str:
    return out.stem.split("_", 1)[0]


def follow_task(
    key: str,
    task_id: str,
    out: Path,
    record: dict,
    record_path: Path,
    interval: int,
    timeout: int,
) -> dict:
    update_record(record_path, record, state="submitted", last_error=None)
    try:
        resp = wait_for(key, task_id, interval, timeout)
        urls = result_urls(resp)
        if not urls:
            raise TaskPendingError("任务成功但没有可解析的结果地址")
    except TaskFailedError as exc:
        update_record(record_path, record, state=TASK_FAILED, last_error=str(exc))
        raise
    except TaskPendingError as exc:
        update_record(record_path, record, state="submitted", last_error=str(exc))
        raise

    update_record(record_path, record, state=DOWNLOAD_PENDING, last_error=None)
    try:
        size = download_with_retry(key, task_id, urls[0], out)
    except DownloadError as exc:
        update_record(record_path, record, state=DOWNLOAD_PENDING, last_error=str(exc))
        raise

    update_record(
        record_path,
        record,
        state=DOWNLOADED_PENDING_QC,
        file=str(out),
        bytes=size,
        last_error=None,
    )
    print(f"  ✓ {out.name}（{size // 1024} KB）", file=sys.stderr)
    return {
        "file": str(out),
        "taskId": task_id,
        "fingerprint": record["fingerprint"],
        "bytes": size,
        "state": DOWNLOADED_PENDING_QC,
    }


def submit_or_resume(
    key: str,
    prompt: str,
    ratio: str,
    resolution: str | None,
    source_refs: list[str],
    callback: str | None,
    out: Path,
    ledger_dir: Path,
    interval: int,
    timeout: int,
    new_attempt: bool = False,
) -> dict:
    fp = request_fingerprint(prompt, ratio, resolution, source_refs)
    record_path = task_record_path(ledger_dir, out, fp)
    record = load_record(record_path)

    if image_file_valid(out):
        if record:
            update_record(
                record_path,
                record,
                state=DOWNLOADED_PENDING_QC,
                file=str(out),
                bytes=out.stat().st_size,
                last_error=None,
            )
        return {
            "file": str(out),
            "taskId": (record or {}).get("task_id"),
            "fingerprint": fp,
            "bytes": out.stat().st_size,
            "state": "skipped_existing",
        }

    if record and record.get("task_id") and not new_attempt:
        if record.get("state") == TASK_FAILED:
            raise TaskFailedError(
                f"原任务已失败，未重新提交；taskId={record['task_id']}，"
                f"记录={record_path}。确认重做时使用 --new-attempt"
            )
        try:
            return follow_task(
                key,
                str(record["task_id"]),
                out,
                record,
                record_path,
                interval,
                timeout,
            )
        except (TaskFailedError, TaskPendingError, DownloadError) as exc:
            setattr(exc, "task_id", record.get("task_id"))
            setattr(exc, "record_path", str(record_path))
            raise

    if record and record.get("state") == TASK_FAILED and not new_attempt:
        raise TaskFailedError(f"原任务已失败，未重新提交：{record_path}")

    refs = []
    for ref in source_refs:
        refs.append(ref if str(ref).startswith(("http://", "https://")) else upload_file(key, Path(ref)))
    body = build_payload(prompt, ratio, resolution, refs, callback)
    task_id = create_task(key, body)

    history = list((record or {}).get("history") or [])
    if record and record.get("task_id"):
        history.append(
            {
                "task_id": record["task_id"],
                "state": record.get("state"),
                "last_error": record.get("last_error"),
                "updated_at": record.get("updated_at"),
            }
        )
    record = {
        "schema_version": 1,
        "asset_id": asset_id_from_output(out),
        "output": str(out),
        "fingerprint": fp,
        "task_id": task_id,
        "state": "submitted",
        "last_error": None,
        "history": history,
        "created_at": (record or {}).get("created_at") or utc_now(),
    }
    # Persist the taskId before waiting or downloading. This is the recovery point.
    write_record(record_path, record)
    print(f"  taskId: {task_id} ｜ ledger: {record_path}", file=sys.stderr)
    try:
        return follow_task(key, task_id, out, record, record_path, interval, timeout)
    except (TaskFailedError, TaskPendingError, DownloadError) as exc:
        setattr(exc, "task_id", task_id)
        setattr(exc, "record_path", str(record_path))
        raise


# ---------------- 子命令 ----------------
def cmd_generate(args) -> int:
    out = Path(args.out).expanduser().resolve()
    source_refs = resolve_refs(args.ref or [], require_exists=not args.dry_run)
    if args.dry_run:
        refs = [
            str(r) if str(r).startswith("http") else f"<本地待上传:{r}>" for r in source_refs
        ]
        body = build_payload(args.prompt, args.ratio, args.resolution, refs, args.callback_url)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        fp = request_fingerprint(args.prompt, args.ratio, args.resolution, source_refs)
        print(f"→ 指纹 {fp} ｜ 预计输出：{out}", file=sys.stderr)
        return 0

    key = api_key(args.api_key)
    result = submit_or_resume(
        key=key,
        prompt=args.prompt,
        ratio=args.ratio,
        resolution=args.resolution,
        source_refs=source_refs,
        callback=args.callback_url,
        out=out,
        ledger_dir=ledger_dir_for(out.parent, args.ledger_dir),
        interval=args.interval,
        timeout=args.timeout,
        new_attempt=args.new_attempt,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_one(item: dict, index: int, total: int, key: str, out_dir: Path,
            dry: bool, interval: int, timeout: int, ledger_dir: Path,
            new_attempt: bool = False) -> dict:
    """跑一张图。返回结果字典，异常由调用方捕获，这里不做 try。"""
    name = item.get("out") or f"task-{index:02d}.png"
    out = out_dir / name
    source_refs = resolve_refs(item.get("ref") or [], out_dir, require_exists=not dry)
    print(f"[{index}/{total}] {name}", file=sys.stderr)

    if dry:
        refs = [
            str(ref) if str(ref).startswith(("http://", "https://")) else f"<本地待上传:{ref}>"
            for ref in source_refs
        ]
        body = build_payload(
            item["prompt"],
            item.get("ratio", "9:16"),
            item.get("resolution") or DEFAULT_RESOLUTION,
            refs,
            None,
        )
        print(json.dumps(body, ensure_ascii=False)[:200] + " …", file=sys.stderr)
        fp = request_fingerprint(
            item["prompt"],
            item.get("ratio", "9:16"),
            item.get("resolution") or DEFAULT_RESOLUTION,
            source_refs,
        )
        return {"file": str(out), "fingerprint": fp, "dry_run": True}

    fp = request_fingerprint(
        item["prompt"],
        item.get("ratio", "9:16"),
        item.get("resolution") or DEFAULT_RESOLUTION,
        source_refs,
    )
    record_path = task_record_path(ledger_dir, out, fp)
    try:
        return submit_or_resume(
            key=key,
            prompt=item["prompt"],
            ratio=item.get("ratio", "9:16"),
            resolution=item.get("resolution") or DEFAULT_RESOLUTION,
            source_refs=source_refs,
            callback=None,
            out=out,
            ledger_dir=ledger_dir,
            interval=interval,
            timeout=timeout,
            new_attempt=new_attempt,
        )
    except (TaskFailedError, TaskPendingError, DownloadError) as exc:
        record = load_record(record_path) or {}
        setattr(exc, "task_id", record.get("task_id"))
        setattr(exc, "record_path", str(record_path))
        raise


def batch_failure(i: int, item: dict, exc: BaseException, out_dir: Path) -> dict:
    name = str(out_dir / (item.get("out") or f"task-{i:02d}.png"))
    result = {"file": name, "error": str(exc)}
    task_id = getattr(exc, "task_id", None)
    record_path = getattr(exc, "record_path", None)
    if task_id:
        result["taskId"] = task_id
    if record_path:
        result["record"] = record_path
    return result


def cmd_batch(args) -> int:
    key = None if args.dry_run else api_key(args.api_key)
    tasks_path = Path(args.tasks)
    if not tasks_path.is_file():
        raise SystemExit(f"任务文件不存在：{tasks_path}")
    try:
        items = json.loads(tasks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"任务文件不是合法 JSON：{exc}")
    if not isinstance(items, list) or not items:
        raise SystemExit("任务文件应是一个非空数组。")

    out_dir = Path(args.out_dir).expanduser().resolve()
    output_names = [item.get("out") or f"task-{i:02d}.png" for i, item in enumerate(items, 1)]
    if len(output_names) != len(set(output_names)):
        raise SystemExit("任务表中存在重复输出文件；每个资产编号只能有一个输出")
    ledger_dir = ledger_dir_for(out_dir, args.ledger_dir)
    if not args.dry_run:
        ledger_dir.mkdir(parents=True, exist_ok=True)
    total = len(items)
    ok, failed = [], []

    # 预演走串行：不花时间，输出也不会互相穿插，好读。
    if args.dry_run or total == 1:
        for i, item in enumerate(items, 1):
            try:
                ok.append(run_one(item, i, total, key, out_dir, args.dry_run,
                                  args.interval, args.timeout, ledger_dir, args.new_attempt))
            except (SystemExit, RuntimeError) as exc:
                failed.append(batch_failure(i, item, exc, out_dir))
                if args.stop_on_error:
                    break
        summary = {"ok": len(ok), "failed": len(failed), "items": ok + failed}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if not failed else 2

    concurrency = max(1, min(args.concurrency, total))
    stop = threading.Event()
    lock = threading.Lock()

    def job(i: int, item: dict):
        if stop.is_set():
            return i, item, None, "跳过（前面已有失败）"
        try:
            return i, item, run_one(item, i, total, key, out_dir, False,
                                     args.interval, args.timeout, ledger_dir,
                                     args.new_attempt), None
        except (SystemExit, RuntimeError) as exc:
            if args.stop_on_error:
                stop.set()
            return i, item, None, exc
        except Exception as exc:  # 网络、解析之类的意外也不能让整批挂掉
            if args.stop_on_error:
                stop.set()
            return i, item, None, f"{type(exc).__name__}: {exc}"

    print(f"批量 {total} 张，并发 {concurrency}，台账 {ledger_dir}", file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(job, i, item) for i, item in enumerate(items, 1)]
        for fut in concurrent.futures.as_completed(futures):
            i, item, result, err = fut.result()
            with lock:
                if result is not None:
                    ok.append(result)
                else:
                    failed.append(batch_failure(i, item, err, out_dir))

    # 按任务顺序输出，方便对着清单核对
    order = {str(out_dir / (it.get("out") or f"task-{i:02d}.png")): i
             for i, it in enumerate(items, 1)}
    merged = sorted(ok + failed, key=lambda r: order.get(r["file"], 0))
    summary = {"ok": len(ok), "failed": len(failed), "items": merged}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


def cmd_query(args) -> int:
    key = api_key(args.api_key)
    resp = query_task(key, args.task_id)
    data = resp.get("data") or {}
    out = {
        "taskId": args.task_id,
        "state": data.get("state"),
        "failMsg": data.get("failMsg"),
        "resultUrls": result_urls(resp),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if result_urls(resp) else 2


def cmd_retrieve(args) -> int:
    """Recover an already-created task without submitting a new one."""
    key = api_key(args.api_key)
    out = Path(args.out).expanduser().resolve()
    ledger_dir = ledger_dir_for(out.parent, args.ledger_dir)
    pair = find_record_by_task(ledger_dir, args.task_id, out)
    if pair is None:
        raise RuntimeError("无法建立恢复记录")
    record_path, record = pair
    write_record(record_path, record)
    try:
        result = follow_task(
            key,
            args.task_id,
            out,
            record,
            record_path,
            args.interval,
            args.timeout,
        )
    except (TaskFailedError, TaskPendingError, DownloadError) as exc:
        setattr(exc, "task_id", args.task_id)
        setattr(exc, "record_path", str(record_path))
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="KIE GPT Image 2 生图执行器")
    ap.add_argument("--api-key", help="临时传入密钥；默认读环境变量 KIE_API_KEY")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--interval", type=int, default=5, help="轮询间隔秒，默认 5")
        p.add_argument("--timeout", type=int, default=600, help="等待上限秒，默认 600")
        p.add_argument("--dry-run", action="store_true", help="只打印请求体，不提交")

    g = sub.add_parser("generate", help="生成一张图并下载")
    g.add_argument("--prompt", required=True)
    g.add_argument("--ratio", default="9:16", help="9:16 / 3:4 / 1:1 / 4:3 / 16:9 / auto")
    g.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        help=f"1K / 2K / 4K，默认 {DEFAULT_RESOLUTION}；4K 不能配 1:1，auto 只能 1K",
    )
    g.add_argument("--ref", action="append", help="参考图，本地路径或 URL，可重复")
    g.add_argument("--out", required=True, help="输出文件路径，建议用 <编号>_<用途>_v<N>.png")
    g.add_argument("--callback-url")
    g.add_argument("--ledger-dir", help=f"任务台账目录，默认输出目录旁 {LEDGER_DIR_NAME}")
    g.add_argument("--new-attempt", action="store_true", help="仅在用户确认重做后创建新任务")
    common(g)
    g.set_defaults(func=cmd_generate)

    b = sub.add_parser("batch", help="按 JSON 批量生成（默认 5 路并发）")
    b.add_argument("--tasks", required=True, help="JSON 数组文件")
    b.add_argument("--out-dir", required=True)
    b.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"同时跑几个，默认 {DEFAULT_CONCURRENCY}；被限流就降到 2–3",
    )
    b.add_argument("--ledger-dir", help=f"任务台账目录，默认素材目录旁 {LEDGER_DIR_NAME}")
    b.add_argument("--new-attempt", action="store_true", help="仅在用户确认整批重做后创建新任务")
    b.add_argument("--stop-on-error", action="store_true", help="有一张失败就不再提交新的")
    common(b)
    b.set_defaults(func=cmd_batch)

    q = sub.add_parser("query", help="查任务状态")
    q.add_argument("--task-id", required=True)
    q.set_defaults(func=cmd_query)

    r = sub.add_parser("retrieve", help="按原 taskId 查询并重新下载，不新建任务")
    r.add_argument("--task-id", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--ledger-dir", help=f"任务台账目录，默认输出目录旁 {LEDGER_DIR_NAME}")
    common(r)
    r.set_defaults(func=cmd_retrieve)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        task_id = getattr(exc, "task_id", None)
        record = getattr(exc, "record_path", None)
        print(f"错误：{exc}", file=sys.stderr)
        if task_id:
            print(f"原 taskId 已保留：{task_id}", file=sys.stderr)
        if record:
            print(f"任务记录：{record}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
