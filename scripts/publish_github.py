#!/usr/bin/env python3
"""Publish ONLY the verified release files into a NEW repository. Dry-run by default."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "IdeaParallax"
TOP_FILES = {"README.md", "LICENSE", "SECURITY.md", "AGENTS.md", "pyproject.toml", ".gitignore", ".env.example"}
PREFIXES = ("idea_parallax/", "tests/", "scripts/", "docs/", "examples/", "configs/", "skills/", ".github/workflows/")

class PublishError(RuntimeError):
    pass

def allowed_path(name: str) -> bool:
    p = PurePosixPath(name)
    return (not p.is_absolute() and ".." not in p.parts and "\\" not in name
            and all(part not in (".git", "__pycache__", ".venv", "runs", "node_modules") for part in p.parts)
            and p.name not in ("auth.json", ".netrc", ".npmrc", ".pypirc", "id_rsa", "id_ed25519", "credentials", "token.json")
            and ".local." not in name and not name.endswith((".pyc", ".pem", ".key", ".log"))
            and not (p.name.startswith(".env") and name != ".env.example")
            and (name in TOP_FILES or name.startswith(PREFIXES)))

def release_files(root: Path) -> list[tuple[str, bytes]]:
    path = root / "release-files.json"
    if not path.is_file() or path.is_symlink():
        raise PublishError("Missing release-files.json; do not publish an unverified working tree")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("project") != NAME or not isinstance(manifest.get("files"), list):
        raise PublishError("Manifest does not identify this standalone project")
    seen, result = set(), []
    for entry in manifest["files"]:
        name = entry["path"]
        if not isinstance(name, str) or not allowed_path(name) or name in seen:
            raise PublishError("Unsafe or duplicate release-file path")
        seen.add(name)
        src = root / name
        relative_parts = [root.joinpath(*PurePosixPath(name).parts[:i]) for i in range(1, len(PurePosixPath(name).parts)+1)]
        if any(p.is_symlink() for p in relative_parts) or not src.is_file() or src.stat().st_size > 8*1024*1024:
            raise PublishError("Release file is missing, oversized or a symlink")
        content = src.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise PublishError("Release file changed; audit and rebuild the manifest before publication")
        result.append((name, content))
    if not TOP_FILES <= seen:
        raise PublishError("Release manifest lacks required project files")
    return result

def checked(args: list[str], cwd: Path | None = None) -> str:
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if p.returncode:
        raise PublishError(f"{args[0]} command failed (exit {p.returncode}); raw output omitted to protect credentials")
    return p.stdout.strip()

def publish(root: Path, owner: str, *, execute: bool = False, public: bool = False) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner):
        raise PublishError("Invalid GitHub owner")
    contents = release_files(root)
    result = {"repository": f"{owner}/{NAME}", "visibility": "public" if public else "private",
              "files": len(contents)+1, "mode": "execute" if execute else "dry_run",
              "safety": "fresh staging repository; no existing repository overwritten; no force push"}
    if not execute:
        return result
    for executable in ("git", "gh"):
        if not shutil.which(executable):
            raise PublishError(f"Missing required executable: {executable}. No repository was created.")
    checked(["gh", "auth", "status"])
    login = checked(["gh", "api", "user", "--jq", ".login"])
    if login.casefold() != owner.casefold():
        raise PublishError("Authenticated account does not match --owner; refusing cross-account publication")
    # Run tests before even asking GitHub to create a repository.
    tested = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=root, timeout=180)
    if tested.returncode:
        raise PublishError("Tests failed; nothing was published")
    with tempfile.TemporaryDirectory(prefix="ideaparallax-publish-") as directory:
        stage = Path(directory)
        for name, data in contents:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (stage / "release-files.json").write_bytes((root / "release-files.json").read_bytes())
        checked(["git", "init", "-b", "main"], stage)
        checked(["git", "config", "user.name", owner], stage)
        checked(["git", "config", "user.email", f"{owner}@users.noreply.github.com"], stage)
        # Scope GitHub credential helper to the throwaway staging repository only.
        checked(["git", "config", "credential.https://github.com.helper", "!gh auth git-credential"], stage)
        checked(["git", "add", "--all"], stage)
        checked(["git", "commit", "-m", "Initial IdeaParallax release with five documented review rounds"], stage)
        sha = checked(["git", "rev-parse", "HEAD"], stage)
        try:
            # gh refuses creation when the repository already exists. Never adopt or overwrite it.
            checked(["gh", "repo", "create", f"{owner}/{NAME}", "--public" if public else "--private",
                     "--description", "Independent parallel research ideation with provenance and evidence-aware review",
                     "--source", str(stage), "--remote", "origin", "--push"], stage)
        except PublishError:
            raise PublishError("Create/push failed. A new empty repository MAY have been created; inspect GitHub. No existing repository was force-pushed or overwritten.") from None
        remote_sha = checked(["gh", "api", f"repos/{owner}/{NAME}/commits/main", "--jq", ".sha"])
        if remote_sha != sha:
            raise PublishError("Remote commit verification failed; publication is not confirmed")
        result.update({"mode": "published_and_verified", "commit": sha, "url": f"https://github.com/{owner}/{NAME}"})
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--public", action="store_true", help="Explicitly make this new repository public (default private)")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(publish(ROOT, args.owner, execute=args.execute, public=args.public), ensure_ascii=False, indent=2))
        return 0
    except (PublishError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc) if isinstance(exc, PublishError) else "Publication preflight failed; no success is claimed", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
