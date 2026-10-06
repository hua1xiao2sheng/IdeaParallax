"""One common output contract, not one common reasoning strategy."""
from __future__ import annotations
import copy
from .io_utils import ValidationError, text, string_list

def obj(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

STR = {"type": "string"}
STRS = {"type": "array", "items": STR}
EXPERIMENT = obj({k: STR for k in ("dataset", "baseline", "metric", "procedure", "falsification")})
CANDIDATE = obj({
    "title": STR, "research_question": STR, "hypothesis": STR, "mechanism": STR,
    "claimed_difference": STR,
    "contribution_type": {"type": "string", "enum": ["method", "diagnostic", "theory", "empirical"]},
    "evidence_ids": STRS, "search_queries": STRS, "experiment": EXPERIMENT,
    "compute_requirement": STR, "risks": STRS,
})
BATCH_SCHEMA = obj({"candidates": {"type": "array", "items": CANDIDATE}, "notes": STR})
ASSESSMENT = obj({
    "idea_id": STR,
    "novelty": {"type": "string", "enum": ["insufficient_evidence", "possible_overlap", "difference_to_investigate"]},
    "feasibility": {"type": "string", "enum": ["unknown", "plausible", "blocked"]},
    "priority": {"type": "string", "enum": ["explore", "needs_work", "defer"]},
    "strengths": STRS, "objections": STRS, "next_checks": STRS, "evidence_ids": STRS,
})
REVIEW_SCHEMA = obj({"assessments": {"type": "array", "items": ASSESSMENT}, "notes": STR})

def validate_schema(value, schema: dict, location: str = "output") -> None:
    """Validate the small strict schema subset used by this package."""
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValidationError(f"Missing/unknown fields in {location}")
        for key, sub in schema["properties"].items():
            validate_schema(value[key], sub, f"{location}.{key}")
    elif kind == "array":
        if not isinstance(value, list) or len(value) > 100:
            raise ValidationError(f"Invalid bounded array in {location}")
        for item in value:
            validate_schema(item, schema["items"], location)
    elif kind == "string":
        text(value, location, maximum=20000, empty=True)
        if "enum" in schema and value not in schema["enum"]:
            raise ValidationError(f"Invalid enumeration in {location}")
    else:
        raise ValidationError("Unsupported schema type")

def validate_brief(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) - {"topic", "constraints", "seed_papers", "language", "context"}:
        raise ValidationError("Unexpected brief fields")
    topic = text(raw.get("topic"), "topic", 15000)
    constraints = string_list(raw.get("constraints", []), "constraints")
    seeds = raw.get("seed_papers", [])
    if not isinstance(seeds, list) or len(seeds) > 50:
        raise ValidationError("seed_papers must be a list of at most 50 records")
    normalized = []
    for index, seed in enumerate(seeds):
        if not isinstance(seed, dict) or set(seed) - {"title", "url", "excerpt"}:
            raise ValidationError("Invalid seed paper")
        normalized.append({"id": f"seed-{index+1:03d}", "title": text(seed.get("title"), "seed title"),
                           "url": text(seed.get("url", ""), "seed url", 2000, True),
                           "excerpt": text(seed.get("excerpt", ""), "excerpt", 20000, True),
                           "status": "user_supplied_not_independently_verified"})
    language = raw.get("language", "zh-CN")
    if language not in ("zh-CN", "en"):
        raise ValidationError("language must be zh-CN or en")
    return {"topic": topic, "constraints": constraints, "seed_papers": normalized,
            "language": language, "context": text(raw.get("context", ""), "context", 30000, True)}

def validate_batch(raw: dict, allowed_evidence: set[str], max_ideas: int) -> dict:
    validate_schema(raw, BATCH_SCHEMA)
    if not raw["candidates"]:
        text(raw["notes"], "reason for no candidates")
    if len(raw["candidates"]) > max_ideas:
        raise ValidationError("Branch exceeded its candidate quota")
    for idea in raw["candidates"]:
        for key in ("title", "research_question", "hypothesis", "mechanism", "claimed_difference", "compute_requirement"):
            text(idea[key], key)
        for key, val in idea["experiment"].items():
            text(val, key)
        if not set(idea["evidence_ids"]) <= allowed_evidence:
            raise ValidationError("Candidate cites evidence outside its registered packet")
        for key in ("evidence_ids", "search_queries", "risks"):
            string_list(idea[key], key)
        if not idea["search_queries"]:
            raise ValidationError("Candidate must supply at least one prior-art search query")
    return raw

def validate_review(raw: dict, idea_ids: set[str], evidence_ids: set[str], metadata_only: bool) -> dict:
    validate_schema(raw, REVIEW_SCHEMA)
    raw = copy.deepcopy(raw)
    records = raw["assessments"]
    if len(records) != len(idea_ids) or {r["idea_id"] for r in records} != idea_ids:
        raise ValidationError("Review must cover every candidate exactly once")
    for record in records:
        if not set(record["evidence_ids"]) <= evidence_ids:
            raise ValidationError("Review references unknown evidence")
        if metadata_only:
            record["novelty"] = "insufficient_evidence"
        if not record["evidence_ids"] and record["novelty"] != "insufficient_evidence":
            record["novelty"] = "insufficient_evidence"
        if not record["next_checks"]:
            raise ValidationError("Review must state a next verification action")
    return raw
