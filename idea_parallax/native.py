"""Export an explicitly trusted pinned repository without modifying the original checkout."""
from __future__ import annotations
import contextlib
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from .io_utils import ValidationError, assert_no_symlinks

MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024

def export_snapshot(repo: Path, commit: str, target: Path) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValidationError("Native project requires a full 40-character commit SHA")
    assert_no_symlinks(target)
    if target.exists():
        raise ValidationError("Native snapshot target must be new")
    target.mkdir(parents=True, mode=0o700)
    process = subprocess.Popen(["git", "-C", str(repo.resolve()), "archive", "--format=tar", commit],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total, count = 0, 0
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                count += 1
                pure = PurePosixPath(member.name)
                if (pure.is_absolute() or ".." in pure.parts or "\\" in member.name or ".git" in pure.parts
                    or not pure.parts or member.issym() or member.islnk() or not (member.isdir() or member.isfile())):
                    raise ValidationError("Unsafe archive entry in native project")
                total += member.size
                if total > MAX_SNAPSHOT_BYTES or count > 20000:
                    raise ValidationError("Native snapshot exceeds 256 MiB or 20,000 entries")
                destination = target.joinpath(*pure.parts)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValidationError("Unreadable native archive file")
                with source, destination.open("xb") as out:
                    remaining = member.size
                    while remaining:
                        chunk = source.read(min(65536, remaining))
                        if not chunk:
                            raise ValidationError("Truncated native archive")
                        out.write(chunk)
                        remaining -= len(chunk)
                # Preserve only executable intent, not ownership or special mode bits.
                destination.chmod(0o700 if member.mode & 0o111 else 0o600)
        if process.wait(timeout=20) != 0:
            raise ValidationError("git archive failed for native project")
    except (tarfile.TarError, OSError, subprocess.TimeoutExpired):
        raise ValidationError("Could not export the pinned native repository") from None
    finally:
        if process.poll() is None:
            process.kill()
        if process.stdout:
            process.stdout.close()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
