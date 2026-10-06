"""Resolve the local Codex CLI without a shell; never read/copy auth.json."""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def codex_command(binary: str = "codex") -> list[str]:
    resolved = shutil.which(binary)
    if not resolved:
        raise RuntimeError("未找到 Codex CLI。请先运行 codex --version，或用 --codex-binary 指定程序路径。")
    path = Path(resolved).absolute()
    # npm's Windows .cmd shim is not a native executable. Invoke its fixed JS
    # entry with Node; never pass model input or filenames through cmd.exe.
    if path.suffix.lower() in (".cmd", ".bat", ".ps1"):
        entry = path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = shutil.which("node")
        if not entry.is_file() or not node:
            raise RuntimeError("Codex 包装脚本不可直接启动；请安装官方 CLI 或指定 codex.exe。")
        return [node, str(entry)]
    return [str(path)]


def subscription_env() -> dict:
    from .providers import safe_env
    env = safe_env({}, codex=True)
    env.pop("OPENAI_API_KEY", None)
    env.pop("CODEX_API_KEY", None)
    return env


def check_codex(binary: str = "codex") -> dict:
    """Only return a classification, not raw authentication output or identifiers."""
    try:
        cmd = codex_command(binary)
    except RuntimeError as exc:
        return {"installed": False, "chatgpt_login": False, "status": "missing", "message": str(exc)}
    try:
        with tempfile.TemporaryDirectory(prefix="parallax-auth-check-") as directory:
            result = subprocess.run(cmd + ["login", "status"], cwd=directory,
                env=subscription_env(), capture_output=True, timeout=12)
        output = (result.stdout + result.stderr).decode("utf-8", "replace").lower()
        # Fail closed on unknown/localized formats. Credentials never go to the UI.
        logged_in = result.returncode == 0 and "chatgpt" in output and "not logged" not in output
        status = "chatgpt" if logged_in else "api_key" if "api key" in output or "api_key" in output else "not_verified"
        message = "已检测到 ChatGPT 登录；模型权限、剩余额度和网络需实际运行确认。" if logged_in else "未确认 ChatGPT 登录。请在同一终端运行 codex login，再点重新检测。"
        return {"installed": True, "chatgpt_login": logged_in, "status": status, "message": message}
    except (OSError, subprocess.SubprocessError):
        return {"installed": True, "chatgpt_login": False, "status": "check_failed", "message": "CLI 登录检测超时或失败；请手动运行 codex login status。"}
