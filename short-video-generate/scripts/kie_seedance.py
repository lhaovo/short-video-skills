#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIE Seedance 视频生成执行器（分镜转片段用）。

只做五件事：拼请求、提交任务、轮询状态、下载到指定路径、批量跑清单。
密钥只从环境变量 KIE_API_KEY 读取，不写入文件、不打印。

用法：
    python kie_seedance.py create --prompt "..." --out 04-素材/03-片段/S01_v1.mp4
    python kie_seedance.py create --prompt "..." --mode first --first 04-素材/02-首帧/S01_f01_v1.png --out out.mp4
    python kie_seedance.py create --prompt "..." --mode first-last --first f.png --last l.png --out out.mp4
    python kie_seedance.py create --prompt "..." --duration 8 --dry-run
    python kie_seedance.py batch --tasks tasks.json --out-dir 04-素材/03-片段 --dry-run
    python kie_seedance.py query --task-id xxx
    python kie_seedance.py wait --task-id xxx --out out.mp4
    python kie_seedance.py upload --file f.png

退出码：0 成功 / 1 参数、网络或任务错误 / 2 批量中有失败项
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import mimetypes
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

MODEL = "bytedance/seedance-2-mini"

# 单段时长硬限：平台只开放 4–15 秒，超了拆镜，短了交后期。
DURATION_MIN, DURATION_MAX = 4, 15

# 默认 720p：竖屏 720×1280 是能交付的底线。480p 只用来试动作和运镜，
# 试完还要重出，反而更费时间，所以不做默认。
DEFAULT_RESOLUTION = "720p"
DEFAULT_RATIO = "9:16"

# 批量默认 5 路并发。一段视频要等几分钟，串行跑 6 段就是半小时以上；
# 并发跑同样的 6 段，总时长约等于最慢的那一段。被限流就降下来。
DEFAULT_CONCURRENCY = 5

MODES = {
    "text": "文生视频",
    "first": "图生视频-首帧",
    "first-last": "图生视频-首尾帧",
}

SUCCESS_STATES = {"success"}
PENDING_STATES = {"waiting", "queuing", "generating"}


# ---------------- 请求 ----------------
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
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误：{exc}") from exc


def ensure_ok(resp: dict) -> dict:
    if resp.get("code") != 200:
        raise RuntimeError("接口返回异常：" + json.dumps(resp, ensure_ascii=False)[:400])
    return resp


def require_key(explicit: str | None) -> str:
    key = explicit or os.environ.get("KIE_API_KEY", "")
    if not key:
        raise SystemExit("缺少 KIE_API_KEY。先设置环境变量，或用 --api-key 临时传入。")
    return key


# ---------------- 上传参考帧 ----------------
def upload_file(key: str, path: Path, upload_path: str = "videos/storyboard") -> str:
    if not path.is_file():
        raise RuntimeError(f"文件不存在：{path}")
    name = path.name
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    boundary = "----kie-seedance-" + uuid.uuid4().hex

    def field(n: str, v: str) -> list[bytes]:
        return [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{n}"\r\n\r\n'.encode(),
            v.encode("utf-8"),
            b"\r\n",
        ]

    parts: list[bytes] = []
    parts += field("uploadPath", upload_path)
    parts += field("fileName", name)
    parts += [
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
    ]
    parts.append(path.read_bytes())
    parts += [b"\r\n", f"--{boundary}--\r\n".encode()]

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
        raise RuntimeError(f"上传失败 HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"上传网络错误：{exc}")

    data = payload.get("data") or {}
    url = data.get("downloadUrl") or data.get("fileUrl")
    if not url:
        raise RuntimeError("上传成功但没拿到地址：" + json.dumps(payload, ensure_ascii=False)[:300])
    return url


# ---------------- 参数与载荷 ----------------
def validate(duration: int, ratio: str, resolution: str, mode: str) -> None:
    if mode not in MODES:
        raise SystemExit(f"未知模式 {mode}，只能是 {', '.join(MODES)}")
    if not DURATION_MIN <= duration <= DURATION_MAX:
        raise SystemExit(
            f"时长必须是 {DURATION_MIN}–{DURATION_MAX} 整数秒，收到 {duration}。"
            "超过上限请拆镜，低于下限交给后期做动效或裁切。"
        )
    if resolution.lower() not in ("480p", "720p"):
        raise SystemExit("分辨率只能是 480p 或 720p。")
    if ratio.lower() == "adaptive" and mode != "text":
        raise SystemExit("adaptive 比例只用于文生视频，图生请写死 9:16 / 16:9。")


def build_payload(
    prompt: str,
    mode: str,
    duration: int,
    ratio: str,
    resolution: str,
    audio: bool,
    first_url: str | None = None,
    last_url: str | None = None,
    web_search: bool = False,
    callback: str | None = None,
) -> dict:
    validate(duration, ratio, resolution, mode)
    inp: dict = {
        "prompt": prompt,
        "generate_audio": audio,
        "resolution": resolution,
        "aspect_ratio": ratio,
        "duration": duration,
    }
    # 三种模式互斥：字段一旦越界就变成另一个模式，必须严格按模式拼。
    if mode == "first":
        if not first_url:
            raise SystemExit("首帧模式必须提供 --first。")
        inp["first_frame_url"] = first_url
    elif mode == "first-last":
        if not first_url or not last_url:
            raise SystemExit("首尾帧模式必须同时提供 --first 和 --last。")
        inp["first_frame_url"] = first_url
        inp["last_frame_url"] = last_url
    else:
        inp["web_search"] = web_search

    payload: dict = {"model": MODEL, "input": inp}
    if callback:
        payload["callBackUrl"] = callback
    return payload


def fingerprint(payload: dict) -> str:
    """请求指纹：只看决定画面的字段，不含 key 与临时 URL。"""
    inp = payload.get("input") or {}
    key_part = {
        "model": payload.get("model"),
        "prompt": inp.get("prompt"),
        "mode": "first-last"
        if inp.get("last_frame_url")
        else ("first" if inp.get("first_frame_url") else "text"),
        "duration": inp.get("duration"),
        "ratio": inp.get("aspect_ratio"),
        "resolution": inp.get("resolution"),
        "audio": inp.get("generate_audio"),
    }
    raw = json.dumps(key_part, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# ---------------- 任务 ----------------
def create_task(key: str, payload: dict) -> str:
    resp = ensure_ok(request_json("POST", BASE_URL + CREATE_PATH, key, payload))
    task_id = (resp.get("data") or {}).get("taskId")
    if not task_id:
        raise RuntimeError("没拿到 taskId：" + json.dumps(resp, ensure_ascii=False)[:300])
    return task_id


def query_task(key: str, task_id: str) -> dict:
    url = BASE_URL + QUERY_PATH + "?" + urllib.parse.urlencode({"taskId": task_id})
    return ensure_ok(request_json("GET", url, key))


def result_urls(resp: dict) -> list[str]:
    data = resp.get("data") or {}
    raw = data.get("resultJson")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        urls = parsed.get("resultUrls")
        if isinstance(urls, list):
            return [str(u) for u in urls]
    for k in ("resultUrls", "result_urls", "urls"):
        urls = data.get(k)
        if isinstance(urls, list):
            return [str(u) for u in urls]
    return []


def wait_for(key: str, task_id: str, interval: int, timeout: int) -> dict:
    deadline = time.time() + timeout
    step = interval
    last = None
    while time.time() < deadline:
        resp = query_task(key, task_id)
        last = resp
        state = (resp.get("data") or {}).get("state")
        if state in SUCCESS_STATES:
            return resp
        if state == "fail":
            data = resp.get("data") or {}
            raise RuntimeError(
                f"任务失败 failCode={data.get('failCode')} failMsg={data.get('failMsg')}"
            )
        time.sleep(step)
        step = min(step + 2, 30)  # 间隔逐步拉长，别一直密集打
    raise RuntimeError("等待超时：" + json.dumps(last or {}, ensure_ascii=False)[:300])


def download(url: str, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=600) as resp:
            out.write_bytes(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"下载失败 HTTP {exc.code}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"下载网络错误：{exc}")
    return out.stat().st_size


# ---------------- 命令 ----------------
def resolve_frame(key: str, path: str | None, dry: bool, label: str) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    if dry:
        return f"<本地待上传:{path}>"
    return upload_file(key, Path(path))


def make_body(args, key: str) -> dict:
    first = resolve_frame(key, getattr(args, "first", None), args.dry_run, "首帧")
    last = resolve_frame(key, getattr(args, "last", None), args.dry_run, "末帧")
    return build_payload(
        prompt=args.prompt,
        mode=args.mode,
        duration=args.duration,
        ratio=args.ratio,
        resolution=args.resolution,
        audio=args.audio,
        first_url=first,
        last_url=last,
        web_search=getattr(args, "web_search", False),
        callback=args.callback_url,
    )


def cmd_create(args) -> int:
    key = "" if args.dry_run else require_key(args.api_key)
    body = make_body(args, key)
    if args.dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print(f"→ 指纹 {fingerprint(body)} ｜ 预计输出 {args.out or '（未指定）'}", file=sys.stderr)
        return 0

    task_id = create_task(key, body)
    print(
        json.dumps(
            {"taskId": task_id, "fingerprint": fingerprint(body), "state": "waiting"},
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.wait and not args.out:
        print("提示：--wait 需要同时给 --out，否则只提交不下载。", file=sys.stderr)
        return 0
    if args.wait and args.out:
        resp = wait_for(key, task_id, args.interval, args.timeout)
        urls = result_urls(resp)
        if not urls:
            raise RuntimeError("任务成功但没有可解析的结果地址，请用 query 复查同一 taskId。")
        size = download(urls[0], Path(args.out))
        print(
            json.dumps(
                {"taskId": task_id, "file": args.out, "bytes": size, "resultUrl": urls[0]},
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def pick_frame(value) -> str | None:
    """任务表里的首帧允许写成字符串或单元素数组，统一取第一个。"""
    if not value:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return str(value)


def run_one(item: dict, index: int, total: int, key: str, out_dir: Path,
            dry: bool, interval: int, timeout: int) -> dict:
    """跑一段。返回结果字典，异常由调用方捕获。"""
    name = item.get("out") or f"clip-{index:02d}.mp4"
    out = out_dir / name
    print(f"[{index}/{total}] {name}", file=sys.stderr)

    first = resolve_frame(key, pick_frame(item.get("first")), dry, "首帧")
    last = resolve_frame(key, pick_frame(item.get("last")), dry, "末帧")
    mode = item.get("mode") or ("first-last" if last else ("first" if first else "text"))
    body = build_payload(
        prompt=item["prompt"],
        mode=mode,
        duration=int(item.get("duration", 5)),
        ratio=item.get("ratio", DEFAULT_RATIO),
        resolution=item.get("resolution", DEFAULT_RESOLUTION),
        audio=bool(item.get("audio", True)),
        first_url=first,
        last_url=last,
    )
    fp = fingerprint(body)
    if dry:
        print(json.dumps(body, ensure_ascii=False)[:180] + " …", file=sys.stderr)
        return {"file": str(out), "fingerprint": fp, "dry_run": True}

    task_id = create_task(key, body)
    resp = wait_for(key, task_id, interval, timeout)
    urls = result_urls(resp)
    if not urls:
        raise RuntimeError("成功但无可下载地址")
    size = download(urls[0], out)
    print(f"  ✓ {name}（{size // 1024} KB）", file=sys.stderr)
    return {"file": str(out), "taskId": task_id, "fingerprint": fp, "bytes": size}


def cmd_batch(args) -> int:
    key = "" if args.dry_run else require_key(args.api_key)
    items = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        raise SystemExit("任务文件应是非空数组。")

    out_dir = Path(args.out_dir)
    total = len(items)
    ok, failed = [], []

    def name_of(i: int, item: dict) -> str:
        return str(out_dir / (item.get("out") or f"clip-{i:02d}.mp4"))

    # 预演和单条走串行：输出不穿插，好读。
    if args.dry_run or total == 1:
        for i, item in enumerate(items, 1):
            try:
                ok.append(run_one(item, i, total, key, out_dir, args.dry_run,
                                  args.interval, args.timeout))
            except (RuntimeError, SystemExit, KeyError) as exc:
                failed.append({"file": name_of(i, item), "error": str(exc)})
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
        except (RuntimeError, SystemExit, KeyError) as exc:
            if args.stop_on_error:
                stop.set()
            return i, item, None, str(exc)
        except Exception as exc:
            if args.stop_on_error:
                stop.set()
            return i, item, None, f"{type(exc).__name__}: {exc}"

    print(f"批量 {total} 段，并发 {concurrency}", file=sys.stderr)
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(job, i, item) for i, item in enumerate(items, 1)]
        for fut in concurrent.futures.as_completed(futures):
            i, item, result, err = fut.result()
            with lock:
                if result is not None:
                    ok.append(result)
                else:
                    failed.append({"file": name_of(i, item), "error": err})

    order = {name_of(i, it): i for i, it in enumerate(items, 1)}
    merged = sorted(ok + failed, key=lambda r: order.get(r["file"], 0))
    summary = {"ok": len(ok), "failed": len(failed), "items": merged}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failed else 2


def cmd_query(args) -> int:
    key = require_key(args.api_key)
    resp = query_task(key, args.task_id)
    data = resp.get("data") or {}
    out = {
        "taskId": data.get("taskId") or args.task_id,
        "state": data.get("state"),
        "failCode": data.get("failCode"),
        "failMsg": data.get("failMsg"),
        "resultUrls": result_urls(resp),
    }
    print(json.dumps({k: v for k, v in out.items() if v}, ensure_ascii=False, indent=2))
    return 0


def cmd_wait(args) -> int:
    key = require_key(args.api_key)
    resp = wait_for(key, args.task_id, args.interval, args.timeout)
    urls = result_urls(resp)
    if not urls:
        raise RuntimeError("任务成功但没有可解析的结果地址。")
    size = download(urls[0], Path(args.out))
    print(
        json.dumps(
            {"taskId": args.task_id, "state": "success", "file": args.out, "bytes": size, "resultUrl": urls[0]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_upload(args) -> int:
    key = require_key(args.api_key)
    print(upload_file(key, Path(args.file), args.upload_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="KIE Seedance 视频生成执行器")
    ap.add_argument("--api-key", help="临时传入密钥；默认读环境变量 KIE_API_KEY")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--interval", type=int, default=6, help="轮询起始间隔秒，默认 6，逐步拉长")
        p.add_argument("--timeout", type=int, default=900, help="等待上限秒，默认 900")
        p.add_argument("--dry-run", action="store_true", help="只打印请求体，不提交")

    c = sub.add_parser("create", help="生成一段并可选等待下载")
    c.add_argument("--prompt", required=True)
    c.add_argument("--mode", choices=list(MODES), default="text")
    c.add_argument("--first", help="首帧，本地路径或 URL")
    c.add_argument("--last", help="末帧，本地路径或 URL")
    c.add_argument("--duration", type=int, default=5, help=f"{DURATION_MIN}–{DURATION_MAX} 整数秒，默认 5")
    c.add_argument("--ratio", default=DEFAULT_RATIO, help="9:16 / 16:9 / 1:1 / 3:4 / 4:3 / 21:9 / adaptive")
    c.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="480p / 720p，默认 720p")
    c.add_argument(
        "--audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="让模型同时生成音频，默认开；要静音用 --no-audio",
    )
    c.add_argument("--web-search", action="store_true", help="仅文生视频可用，默认关")
    c.add_argument("--callback-url")
    c.add_argument("--out")
    c.add_argument("--wait", action="store_true", help="提交后一直等到下载完成")
    common(c)
    c.set_defaults(func=cmd_create)

    b = sub.add_parser("batch", help="按 JSON 任务表批量生成（默认 5 路并发）")
    b.add_argument("--tasks", required=True)
    b.add_argument("--out-dir", required=True)
    b.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"同时跑几段，默认 {DEFAULT_CONCURRENCY}；被限流就降到 2–3",
    )
    b.add_argument("--stop-on-error", action="store_true", help="有一段失败就不再提交新的")
    common(b)
    b.set_defaults(func=cmd_batch)

    q = sub.add_parser("query", help="查任务状态")
    q.add_argument("--task-id", required=True)
    q.set_defaults(func=cmd_query)

    w = sub.add_parser("wait", help="等任务完成并下载")
    w.add_argument("--task-id", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--interval", type=int, default=6)
    w.add_argument("--timeout", type=int, default=900)
    w.set_defaults(func=cmd_wait)

    u = sub.add_parser("upload", help="上传本地参考帧，拿临时地址")
    u.add_argument("--file", required=True)
    u.add_argument("--upload-path", default="videos/storyboard")
    u.set_defaults(func=cmd_upload)
    return ap


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
