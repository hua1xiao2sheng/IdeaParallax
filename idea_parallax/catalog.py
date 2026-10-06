from __future__ import annotations
from importlib.resources import files
import json
from .io_utils import safe_id, ValidationError

def catalog() -> dict:
    return json.loads(files("idea_parallax").joinpath("data/catalog.json").read_text(encoding="utf-8"))

def strategy(name: str) -> tuple[dict, str]:
    safe_id(name)
    entry = catalog().get(name)
    if entry is None:
        raise ValidationError("Unknown strategy; use the catalog command")
    content = files("idea_parallax").joinpath(f"data/strategies/{name}.md").read_text(encoding="utf-8")
    return entry, content
