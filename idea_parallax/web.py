"""Single-user, loopback-only dashboard. The browser never receives model credentials."""
from __future__ import annotations
import asyncio
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
import uuid
import webbrowser
from .catalog import catalog
from .codex_host import check_codex
from .config import validate_config
from .contracts import validate_brief
from .engine import Engine
from .io_utils import ValidationError, assert_no_symlinks, integer, load_json, parse_model_json, text, write_json

RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
MAX_BODY = 512_000
MAX_EXPORT = 16 * 1024 * 1024


def make_task(raw: dict, binary: str = "codex") -> dict:
    allowed = {"brief", "strategies", "mode", "model", "concurrency", "max_ideas", "review", "retrieval", "consent"}
    if not isinstance(raw, dict) or set(raw) - allowed:
        raise ValidationError("不支持的网页任务字段。")
    mode = raw.get("mode", "demo")
    if mode not in ("demo", "codex"):
        raise ValidationError("网页只支持 demo 或 codex；不会执行任意外部命令。")
    if mode == "codex" and raw.get("consent") is not True:
        raise ValidationError("请确认使用本机 Codex 账号并消耗相应额度。")
    brief = raw.get("brief")
    validate_brief(brief)  # Validate while preserving the original, resumable input.
    selected = raw.get("strategies", list(catalog()))
    if (not isinstance(selected, list) or not 1 <= len(selected) <= 6 or
        any(not isinstance(k, str) or k not in catalog() for k in selected) or len(set(selected)) != len(selected)):
        raise ValidationError("请选择 1–6 个不重复的策略。")
    n = integer(raw.get("max_ideas", 2), "max_ideas", 1, 3)
    parallel = integer(raw.get("concurrency", 2), "concurrency", 1, 6)
    review = raw.get("review", True)
    if type(review) is not bool:
        raise ValidationError("review must be boolean")
    retrieval = raw.get("retrieval", "none")
    if retrieval not in ("none", "crossref"):
        raise ValidationError("不支持的检索方式。")
    if mode == "demo":
        retrieval = "none"
    provider = {"type": "demo"} if mode == "demo" else {
        "type": "codex", "model": text(raw.get("model", ""), "model", 150, True),
        "codex_binary": binary, "subscription_only": True, "timeout_seconds": 900}
    config = {"provider": provider, "concurrency": parallel,
        "max_calls": len(selected) + (2 if review else 0), "retries": 0, "review": review,
        "branches": [{"id": k, "strategy": k, "max_ideas": 1 if k == "ideaspark" else n} for k in selected]}
    validate_config(config)
    return {"brief": copy.deepcopy(brief), "config": config, "retrieval": retrieval, "mode": mode}


class Dashboard:
    def __init__(self, root: Path, binary: str = "codex"):
        assert_no_symlinks(root)
        self.root = root.absolute()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.binary = binary
        self.lock = threading.RLock()
        self.active: str | None = None
        self.stop_requested: str | None = None
        self.task: asyncio.Task | None = None
        self.future = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def directory(self, ident: str) -> Path:
        if not RUN_ID.fullmatch(ident):
            raise ValidationError("无效的任务 ID。")
        target = self.root / ident
        assert_no_symlinks(target)
        return target

    def _meta(self, ident: str) -> dict:
        return load_json(self.directory(ident) / "job.json")

    def _status(self, ident: str, status: str, error: str = ""):
        with self.lock:
            meta = self._meta(ident)
            meta.update(status=status, error=error)
            write_json(self.directory(ident) / "job.json", meta)

    def start(self, raw: dict) -> str:
        spec = make_task(raw, self.binary)
        if spec["mode"] == "codex":
            auth = check_codex(self.binary)
            if not auth["chatgpt_login"]:
                raise ValidationError(auth["message"])
        with self.lock:
            if self.active:
                raise ValidationError("已有一个任务正在运行。请等它完成或先停止；任务内部支持多分支并行。")
            if sum(1 for p in self.root.iterdir() if p.is_dir()) >= 200:
                raise ValidationError("此存储目录已达到 200 个任务，请用 --data-dir 选择新的目录。")
            ident = uuid.uuid4().hex
            directory = self.directory(ident)
            directory.mkdir(mode=0o700)
            write_json(directory / "job.json", {"id": ident, "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "starting", "error": "", "spec": spec})
            self._schedule(ident, False)
            return ident

    def _schedule(self, ident: str, resume: bool):
        self.active, self.stop_requested = ident, None
        self.future = asyncio.run_coroutine_threadsafe(self._execute(ident, resume), self.loop)

    async def _execute(self, ident: str, resume: bool):
        self.task = asyncio.current_task()
        try:
            if self.stop_requested == ident:
                raise asyncio.CancelledError
            self._status(ident, "running")
            spec = self._meta(ident)["spec"]
            report = await Engine(spec["brief"], spec["config"], self.directory(ident) / "run",
                                  retrieval=spec["retrieval"]).run(resume=resume)
            self._status(ident, report["status"])
        except asyncio.CancelledError:
            self._status(ident, "interrupted")
        except Exception as exc:
            # Do not leak arbitrary exception text or credentials through HTTP.
            self._status(ident, "failed", str(exc) if isinstance(exc, ValidationError) else
                         f"任务失败（{type(exc).__name__}）；原始异常不在网页显示。")
        finally:
            with self.lock:
                self.active, self.task, self.stop_requested = None, None, None

    def stop(self, ident: str):
        with self.lock:
            if self.active != ident:
                raise ValidationError("此任务不在运行中。")
            self.stop_requested = ident
            self._status(ident, "stopping")
            def cancel():
                if self.active == ident and self.task:
                    self.task.cancel()
            self.loop.call_soon_threadsafe(cancel)

    def resume(self, ident: str):
        with self.lock:
            if self.active:
                raise ValidationError("已有任务正在运行。")
            meta = self._meta(ident)
            if meta["spec"]["mode"] == "codex":
                auth = check_codex(self.binary)
                if not auth["chatgpt_login"]:
                    raise ValidationError(auth["message"])
            run = self.directory(ident) / "run"
            if not (run / "manifest.json").is_file():
                raise ValidationError("没有可续跑的检查点，请新建任务。")
            if (run / ".lock").exists():
                raise ValidationError("检测到运行锁；请先确认旧进程已退出。不会自动删除锁。")
            state = load_json(run / "state.json")
            if state["calls_reserved"] >= meta["spec"]["config"]["max_calls"]:
                raise ValidationError("此任务的调用预算已用完；请新建任务，不会自动追加额度。")
            self._status(ident, "starting")
            self._schedule(ident, True)

    def snapshot(self, ident: str, detail: bool = True) -> dict:
        with self.lock:
            meta = self._meta(ident)
            active = self.active == ident
        spec = meta["spec"]
        status = meta["status"]
        if status in ("starting", "running", "stopping") and not active:
            status = "interrupted"
        run = self.directory(ident) / "run"
        state = load_json(run / "state.json") if (run / "state.json").exists() else {}
        result = {"id": ident, "created_at": meta["created_at"], "topic": spec["brief"]["topic"],
            "mode": spec["mode"], "status": status, "error": meta["error"], "active": active,
            "calls": state.get("calls_reserved", 0), "max_calls": spec["config"]["max_calls"],
            "concurrency": spec["config"]["concurrency"]}
        if not detail:
            return result
        stages, candidates = [], []
        names = [("generate-"+b["id"], catalog()[b["strategy"]]["name"]) for b in spec["config"]["branches"]]
        if spec["config"]["review"]:
            names += [("review-scientific", "科研价值评审"), ("review-feasibility", "可行性评审")]
        for name, label in names:
            stage_status = state.get("stages", {}).get(name, "pending")
            if not active and stage_status in ("running", "queued", "retrying"):
                stage_status = "interrupted"
            item = {"id": name, "label": label, "status": stage_status, "error": ""}
            path = run / "stages" / name / "result.json"
            if path.is_file():
                record = load_json(path)
                item["error"] = record.get("error", "")
                item["usage"] = record.get("usage", {})
                for index, idea in enumerate(record.get("output", {}).get("candidates", [])):
                    candidates.append({**idea, "id": f"{name}-{index}", "source": label, "reviews": []})
            stages.append(item)
        report = None
        # Avoid showing an old final report as current while resuming.
        if not active and (run / "report.json").is_file():
            report = load_json(run / "report.json")
            if status == "interrupted":
                report = None
        if report:
            from .report import assessments
            candidates = [{**idea, "source": catalog()[idea["provenance"]["strategy"]]["name"],
                "reviews": assessments(report, idea["id"])} for idea in report["candidates"]]
        result.update(stages=stages, candidates=candidates, report_ready=bool(report),
            retrieval=spec["retrieval"], retrieval_status=report["retrieval_status"] if report else "not_finished",
            can_resume=not active and (run / "manifest.json").is_file() and
                result["calls"] < result["max_calls"] and status != "completed")
        return result

    def history(self) -> list[dict]:
        records = []
        for path in self.root.iterdir():
            if RUN_ID.fullmatch(path.name) and path.is_dir() and not path.is_symlink():
                try:
                    records.append(self.snapshot(path.name, False))
                except (OSError, ValueError, KeyError):
                    continue
        return sorted(records, key=lambda r: r["created_at"], reverse=True)

    def export(self, ident: str, name: str) -> bytes:
        if name not in ("report.html", "report.json", "report.md"):
            raise ValidationError("不允许导出此路径。")
        if not self.snapshot(ident)["report_ready"]:
            raise ValidationError("当前结果尚未完成，不能下载旧报告。")
        path = self.directory(ident) / "run" / name
        assert_no_symlinks(path)
        if path.stat().st_size > MAX_EXPORT:
            raise ValidationError("报告超出网页下载大小限制。")
        return path.read_bytes()

    def close(self):
        with self.lock:
            active = self.active
        if active:
            self.stop(active)
        if self.future:
            self.future.result(timeout=25)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        if not self.thread.is_alive():
            self.loop.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, dashboard: Dashboard, port: int):
        self.dashboard = dashboard
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.host = f"127.0.0.1:{self.server_port}"
        self.origin = "http://" + self.host


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No prompts, tokens, authentication output or URLs in request logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send(self, status: int, body: bytes, kind: str = "application/json; charset=utf-8", attachment: str = ""):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(body)

    def json(self, value: dict | list, status: int = 200):
        self.send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def gate(self, api: bool):
        if self.headers.get("Host") != self.server.host:
            raise PermissionError("Host 不匹配。请使用启动时显示的 127.0.0.1 地址。")
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            raise PermissionError("拒绝跨站请求。")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise PermissionError("拒绝跨站请求。")
        if api and not secrets.compare_digest(self.headers.get("X-Parallax-Token", ""), self.server.token):
            raise PermissionError("会话未授权。请从终端重新打开包含 #token= 的完整地址。")

    def do_GET(self):
        self.dispatch(False)

    def do_POST(self):
        self.dispatch(True)

    def dispatch(self, post: bool):
        try:
            path = urlsplit(self.path).path
            self.gate(path.startswith("/api/"))
            if not post and path in ("/", "/app.js", "/style.css"):
                name, kind = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                              "/style.css": ("style.css", "text/css")}[path]
                self.send(200, files("idea_parallax").joinpath("data/web/"+name).read_bytes(), kind+"; charset=utf-8")
                return
            data = {}
            if post:
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    raise ValidationError("需要 application/json。")
                if self.headers.get("Transfer-Encoding"):
                    raise ValidationError("不支持分块请求。")
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_BODY:
                    raise ValidationError("请求为空或过大。")
                data = parse_model_json(self.rfile.read(length).decode("utf-8"))
            dash = self.server.dashboard
            if path == "/api/info" and not post:
                self.json({"catalog": catalog(), "python_min": "3.11", "codex": check_codex(dash.binary)})
            elif path == "/api/jobs":
                self.json({"id": dash.start(data)}, 201) if post else self.json(dash.history())
            else:
                match = re.fullmatch(r"/api/jobs/([0-9a-f]{32})(?:/(stop|resume|export/(report\.(?:html|json|md))))?", path)
                if not match:
                    self.json({"error": "没有此接口。"}, 404)
                    return
                ident, action, filename = match.groups()
                if not post and not action:
                    self.json(dash.snapshot(ident))
                elif not post and filename:
                    self.send(200, dash.export(ident, filename), "application/octet-stream", filename)
                elif post and action in ("stop", "resume"):
                    getattr(dash, action)(ident)
                    self.json({"ok": True})
                else:
                    self.json({"error": "不支持的请求方法。"}, 405)
        except PermissionError as exc:
            self.json({"error": str(exc)}, 403)
        except FileNotFoundError:
            self.json({"error": "找不到任务或报告。"}, 404)
        except (ValidationError, ValueError, UnicodeError) as exc:
            self.json({"error": str(exc) if isinstance(exc, ValidationError) else "无效请求。"}, 400)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.json({"error": "服务端错误；请检查本地目录。原始异常未公开。"}, 500)


def serve(root: Path, port: int = 8765, open_browser: bool = False, binary: str = "codex"):
    dash = Dashboard(root, binary)
    try:
        server = Server(dash, port)
    except BaseException:
        dash.close()
        raise
    url = server.origin + "/#token=" + server.token
    print("IdeaParallax 本地界面（勿共享此地址）：\n" + url, flush=True)
    print("登录在终端执行 codex login。关闭终端会停止任务；已完成检查点保留。", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("正在停止本地任务……", flush=True)
    finally:
        server.server_close()
        dash.close()
