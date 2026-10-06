"""Explicit import of pinned, local UTF-8 instruction files; never executes upstream code."""
from __future__ import annotations
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
from .io_utils import ValidationError, write_json, load_json, text, digest

MAX_BUNDLE_BYTES = 240000

def import_bundle(repo: Path, commit: str, paths: list[str], out: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValidationError("Use a full 40-character Git commit SHA, not a moving branch")
    if out.exists():
        raise ValidationError("Bundle output already exists; create a new version")
    if not paths or len(paths) > 40:
        raise ValidationError("Import 1–40 explicit files, including needed references")
    records, size = [], 0
    for path in paths:
        pp = PurePosixPath(path)
        if pp.is_absolute() or ".." in pp.parts or "\\" in path or pp.suffix.lower() not in (".md", ".txt"):
            raise ValidationError("Only safe relative .md/.txt paths may be imported")
        # Check blob size before capturing content into memory.
        info = subprocess.run(["git", "-C", str(repo.resolve()), "cat-file", "-s", f"{commit}:{path}"],
                              capture_output=True, timeout=20, check=False)
        try:
            blob_size = int(info.stdout.strip())
        except ValueError:
            raise ValidationError("Pinned upstream file was not found") from None
        if info.returncode or size + blob_size > MAX_BUNDLE_BYTES:
            raise ValidationError("Upstream instruction bundle exceeds size limit")
        result = subprocess.run(["git", "-C", str(repo.resolve()), "show", f"{commit}:{path}"],
                                capture_output=True, timeout=20, check=False)
        if result.returncode:
            raise ValidationError("Pinned upstream file was not found")
        size += len(result.stdout)
        if size > MAX_BUNDLE_BYTES:
            raise ValidationError("Upstream instruction bundle exceeds size limit")
        try:
            content = result.stdout.decode("utf-8")
        except UnicodeError:
            raise ValidationError("Upstream instructions must be UTF-8") from None
        records.append({"path": path, "sha256": hashlib.sha256(result.stdout).hexdigest(), "content": content})
    manifest = {"commit": commit, "mode": "upstream_instructions_not_native_workflow", "files": records,
                "warning": "Imported instructions only. Dependent tools/scripts are NOT executed. Review license and content before use."}
    manifest["sha256"] = digest(manifest)
    write_json(out, manifest)
    return manifest

def read_bundle(path: Path) -> dict:
    raw = load_json(path)
    if not isinstance(raw, dict) or set(raw) != {"commit", "mode", "files", "warning", "sha256"}:
        raise ValidationError("Invalid upstream bundle")
    check = {k: v for k, v in raw.items() if k != "sha256"}
    if digest(check) != raw["sha256"]:
        raise ValidationError("Upstream bundle changed after import")
    if not re.fullmatch(r"[0-9a-f]{40}", raw["commit"]):
        raise ValidationError("Invalid upstream commit")
    if raw["mode"] != "upstream_instructions_not_native_workflow" or not isinstance(raw["files"], list) or not 1 <= len(raw["files"]) <= 40:
        raise ValidationError("Invalid upstream bundle mode or file count")
    size = 0
    for record in raw["files"]:
        content = text(record["content"], "upstream instructions", MAX_BUNDLE_BYTES, True)
        size += len(content.encode("utf-8"))
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != record["sha256"]:
            raise ValidationError("Upstream file checksum mismatch")
    if size > MAX_BUNDLE_BYTES:
        raise ValidationError("Upstream bundle exceeds input limit")
    return raw
