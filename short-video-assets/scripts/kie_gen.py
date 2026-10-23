#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIE GPT Image 2 生图执行器（资产准备用）。

只做四件事：提交任务、轮询状态、下载到指定路径、按命名落盘。
密钥只从环境变量 KIE_API_KEY 读取，不写入文件、不打印。

用法：
    python kie_gen.py generate --prompt "..." --ratio 9:16 --out 04-素材/01-资产图/PR-01_产品主图_v1.png
    python kie_gen.py generate --prompt "..." --ref 锚点.png --ratio 9:16 --out out.png
    python kie_gen.py generate --prompt "..." --dry-run          # 只看 payload，不花钱
    python kie_gen.py batch --tasks tasks.json --out-dir 04-素材/01-资产图
    python kie_gen.py query --task-id xxx

退出码：0 成功 / 1 参数、网络或任务错误 / 2 批量中有失败项
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
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

# 批量默认 5 路并发。出图主要是等接口返回，线程池足够，不需要改成异步。
# 被限流（429 或返回 code != 200）时把并发降下来再跑。
DEFAULT_CONCURRENCY = 5

SUCCESS_STATES = {"success", "succeed", "succeeded", "completed", "finished"}
FAIL_STATES = {"fail", "failed", "error", "cancelled", "canceled"}


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
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return []
    urls = parsed.get("resultUrls")
    return urls if isinstance(urls, list) else []


def wait_for(key: str, task_id: str, interval: int, timeout: int) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        resp = query_task(key, task_id)
        data = resp.get("data") or {}
        state = str(data.get("state", "")).lower()
        if state != last:
            print(f"  状态：{state or '未知'}", file=sys.stderr)
            last = state
        if result_urls(resp):
            return resp
        if state in FAIL_STATES:
            raise SystemExit(f"任务失败：{data.get('failMsg') or data.get('failCode') or state}")
        if state in SUCCESS_STATES and not result_urls(resp):
            raise SystemExit("任务已成功但没返回图片地址，检查一下输入参数是否被模型拒绝。")
        time.sleep(interval)
    raise SystemExit(f"等待超时（{timeout}s）。可用 query --task-id {task_id} 继续查。")


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=180) as resp, tmp.open("wb") as fh:
            fh.write(resp.read())
    except urllib.error.URLError as exc:
        raise SystemExit(f"下载失败：{exc}")
    tmp.replace(out)


# ---------------- 子命令 ----------------
def cmd_generate(args) -> int:
    if args.dry_run:
        refs = [
            str(r) if str(r).startswith("http") else f"<本地待上传:{r}>" for r in (args.ref or [])
        ]
        body = build_payload(args.prompt, args.ratio, args.resolution, refs, args.callback_url)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print(f"→ 预计输出：{args.out or '（未指定）'}", file=sys.stderr)
        return 0

    key = api_key(args.api_key)
    refs = []
    for ref in args.ref or []:
        refs.append(ref if ref.startswith("http") else upload_file(key, Path(ref)))
    body = build_payload(args.prompt, args.ratio, args.resolution, refs, args.callback_url)

    task_id = create_task(key, body)
    print(f"taskId: {task_id}", file=sys.stderr)
    resp = wait_for(key, task_id, args.interval, args.timeout)
    urls = result_urls(resp)
    if not urls:
        raise SystemExit("没拿到图片地址。")

    out = Path(args.out) if args.out else Path(f"{task_id}.png")
    download(urls[0], out)
    print(json.dumps({"taskId": task_id, "file": str(out), "urls": urls}, ensure_ascii=False, indent=2))
    return 0


def run_one(item: dict, index: int, total: int, key: str, out_dir: Path,
            dry: bool, interval: int, timeout: int) -> dict:
    """跑一张图。返回结果字典，异常由调用方捕获，这里不做 try。"""
    name = item.get("out") or f"task-{index:02d}.png"
    out = out_dir / name
    print(f"[{index}/{total}] {name}", file=sys.stderr)

    refs = []
    for ref in item.get("ref") or []:
        if dry:
            refs.append(str(ref) if str(ref).startswith("http") else f"<本地待上传:{ref}>")
        else:
            refs.append(ref if str(ref).startswith("http") else upload_file(key, Path(ref)))

    body = build_payload(
        item["prompt"],
        item.get("ratio", "9:16"),
        item.get("resolution") or DEFAULT_RESOLUTION,
        refs,
        None,
    )
    if dry:
        print(json.dumps(body, ensure_ascii=False)[:200] + " …", file=sys.stderr)
        return {"file": str(out), "dry_run": True}

    task_id = create_task(key, body)
    resp = wait_for(key, task_id, interval, timeout)
    urls = result_urls(resp)
    download(urls[0], out)
    print(f"  ✓ {name}", file=sys.stderr)
    return {"file": str(out), "taskId": task_id}


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

    out_dir = Path(args.out_dir)
    total = len(items)
    ok, failed = [], []

    # 预演走串行：不花时间，输出也不会互相穿插，好读。
    if args.dry_run or total == 1:
        for i, item in enumerate(items, 1):
            try:
                ok.append(run_one(item, i, total, key, out_dir, args.dry_run,
                                  args.interval, args.timeout))
            except SystemExit as exc:
                failed.append({"file": str(out_dir / (item.get("out") or f"task-{i:02d}.png")), "error": str(exc)})
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
                                     args.interval, args.timeout), None
        except SystemExit as exc:
            if args.stop_on_error:
                stop.set()
            return i, item, None, str(exc)
        except Exception as exc:  # 网络、解析之类的意外也不能让整批挂掉
            if args.stop_on_error:
                stop.set()
            return i, item, None, f"{type(exc).__name__}: {exc}"

    print(f"批量 {total} 张，并发 {concurrency}", file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(job, i, item) for i, item in enumerate(items, 1)]
        for fut in concurrent.futures.as_completed(futures):
            i, item, result, err = fut.result()
            name = str(out_dir / (item.get("out") or f"task-{i:02d}.png"))
            with lock:
                if result is not None:
                    ok.append(result)
                else:
                    failed.append({"file": name, "error": err})

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
    g.add_argument("--out", help="输出文件路径，建议用 <编号>_<用途>_v<N>.png")
    g.add_argument("--callback-url")
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
    b.add_argument("--stop-on-error", action="store_true", help="有一张失败就不再提交新的")
    common(b)
    b.set_defaults(func=cmd_batch)

    q = sub.add_parser("query", help="查任务状态")
    q.add_argument("--task-id", required=True)
    q.set_defaults(func=cmd_query)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
