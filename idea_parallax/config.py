from __future__ import annotations
import copy
from .catalog import strategy
from .io_utils import ValidationError, integer, safe_id, text

def validate_config(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) - {"provider", "reviewer", "concurrency", "max_calls", "retries", "review", "branches"}:
        raise ValidationError("Unexpected configuration fields")
    config = copy.deepcopy(raw)
    config["provider"] = provider_config(raw.get("provider", {"type": "codex"}))
    reviewer_default = config["provider"]
    if reviewer_default["type"] == "native-codex":
        reviewer_default = {k: v for k, v in reviewer_default.items()
                            if k in ("model", "timeout_seconds", "max_output_tokens", "codex_binary", "env_allowlist")}
        reviewer_default["type"] = "codex"
    config["reviewer"] = provider_config(raw.get("reviewer", reviewer_default))
    if config["reviewer"]["type"] == "native-codex":
        raise ValidationError("Use codex/api/command for independent review, not a native ideation workflow")
    config["concurrency"] = integer(raw.get("concurrency", 3), "concurrency", 1, 16)
    config["max_calls"] = integer(raw.get("max_calls", 20), "max_calls", 1, 500)
    config["retries"] = integer(raw.get("retries", 1), "retries", 0, 3)
    config["review"] = raw.get("review", True)
    if type(config["review"]) is not bool:
        raise ValidationError("review must be boolean")
    branches = raw.get("branches")
    if not isinstance(branches, list) or not 1 <= len(branches) <= 20:
        raise ValidationError("Configure between 1 and 20 branches")
    seen = set()
    for branch in config["branches"]:
        if not isinstance(branch, dict) or set(branch) - {"id", "strategy", "max_ideas", "provider", "upstream_bundle"}:
            raise ValidationError("Unexpected branch fields")
        ident = safe_id(branch.get("id"))
        if ident in seen:
            raise ValidationError("Duplicate branch identifier")
        seen.add(ident)
        strategy(branch.get("strategy"))
        branch["max_ideas"] = integer(branch.get("max_ideas", 3), "max_ideas", 1, 5)
        if "provider" in branch:
            branch["provider"] = provider_config(branch["provider"])
        if "upstream_bundle" in branch:
            text(branch["upstream_bundle"], "upstream_bundle", 4000)
    return config

def provider_config(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) - {"type", "model", "base_url", "api_key_env", "timeout_seconds", "max_output_tokens", "command", "env_allowlist", "codex_binary", "repository_path", "commit", "entry", "allow_network", "subscription_only"}:
        raise ValidationError("Unknown provider field (never place secrets in config)")
    p = copy.deepcopy(raw)
    import re
    allowlist = p.get("env_allowlist", [])
    if (not isinstance(allowlist, list) or len(allowlist) > 30 or
        any(not isinstance(k, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,100}", k) for k in allowlist)):
        raise ValidationError("env_allowlist must contain environment variable names")
    if type(p.get("subscription_only", False)) is not bool:
        raise ValidationError("subscription_only must be boolean")
    if "codex_binary" in p:
        text(p["codex_binary"], "codex_binary", 4000)
    if p.get("type") not in ("codex", "api", "demo", "command", "native-codex"):
        raise ValidationError("provider.type must be codex, api, demo, command, or native-codex")
    p["model"] = text(p.get("model", ""), "model", 150, True)
    p["timeout_seconds"] = integer(p.get("timeout_seconds", 120), "timeout_seconds", 1, 3600)
    p["max_output_tokens"] = integer(p.get("max_output_tokens", 6000), "max_output_tokens", 128, 50000)
    if p["type"] == "api":
        if not p["model"] or p["model"] == "CHANGE_ME":
            raise ValidationError("Set an available model for API mode")
        text(p.get("base_url"), "base_url", 2000)
        key = p.get("api_key_env", "IDEA_LLM_API_KEY")
        import re
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", key):
            raise ValidationError("api_key_env must name an environment variable")
        p["api_key_env"] = key
    if p["type"] == "native-codex":
        from pathlib import PurePosixPath
        text(p.get("repository_path"), "repository_path", 4000)
        sha = p.get("commit", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValidationError("native-codex requires a full commit SHA")
        entry = text(p.get("entry"), "entry", 4000)
        pp = PurePosixPath(entry)
        if pp.is_absolute() or ".." in pp.parts or "\\" in entry:
            raise ValidationError("Native entry must be a safe relative path")
        if type(p.get("allow_network", False)) is not bool:
            raise ValidationError("allow_network must be boolean")
    if p["type"] == "command":
        command = p.get("command")
        if not isinstance(command, list) or not command or len(command) > 40:
            raise ValidationError("command must be an argument array, never a shell string")
        for arg in command:
            text(arg, "command argument", 4000)
    return p
