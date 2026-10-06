"""Bounded, atomic storage. Exceptions deliberately omit untrusted data."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

MAX_JSON_BYTES = 4 * 1024 * 1024

# Windows cannot always replace a file while another thread holds a read handle.
# Dashboard polling and engine checkpoints share these helpers in one process.
# Serialize only the brief local I/O operation, not model calls or HTTP work.
_STORAGE_LOCK = threading.RLock()

class ValidationError(ValueError):
    """Invalid task, configuration, or model output."""

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def assert_no_symlinks(path: Path) -> None:
    """Reject existing symlink components before resolving a workspace/storage path."""
    absolute = Path(os.path.abspath(path))
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ValidationError("Symlink path components are not permitted")

def unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON keys are not permitted")
        result[key] = value
    return result

def load_json(path: Path) -> Any:
    with _STORAGE_LOCK:
        assert_no_symlinks(path)
        if path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
            raise ValidationError("JSON file is a symlink or exceeds the size limit")
        try:
            return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValidationError("Non-finite JSON number")))
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValidationError("Invalid UTF-8 JSON file") from exc

def write_text(path: Path, text: str) -> None:
    with _STORAGE_LOCK:
        assert_no_symlinks(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValidationError("Refusing to replace a symlink")
        fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

def safe_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value):
        raise ValidationError("Identifiers must match [a-z][a-z0-9_-]{0,63}")
    return value

def text(value: Any, name: str, maximum: int = 12000, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValidationError(f"Invalid text field: {name}")
    return value

def integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValidationError(f"Invalid integer field: {name}")
    return value

def string_list(value: Any, name: str, maximum: int = 30) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValidationError(f"Invalid list field: {name}")
    return [text(item, name, 6000) for item in value]

def parse_model_json(value: str) -> dict:
    if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValidationError("Model output exceeds the limit")
    value = value.strip()
    if value.startswith("```json\n") and value.endswith("```"):
        value = value[8:-3].strip()
    try:
        result = json.loads(value, object_pairs_hook=unique_object, parse_constant=lambda _: (_ for _ in ()).throw(ValidationError("Non-finite number")))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValidationError("Model did not return a single JSON object") from exc
    if not isinstance(result, dict):
        raise ValidationError("Expected a JSON object")
    return result
