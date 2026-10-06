"""Conservative structural dedup. Lexical similarity is a suggestion, not semantic proof."""
from __future__ import annotations
from collections import defaultdict
import re
import unicodedata
from .io_utils import digest

def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip().casefold())

def structural_key(idea: dict) -> str:
    return digest([normalize(idea[k]) for k in ("research_question", "hypothesis", "mechanism")]
                  + [idea["contribution_type"]] + [normalize(idea["experiment"][k]) for k in sorted(idea["experiment"])])

def grams(value: str) -> set[str]:
    value = normalize(value)
    return {value[i:i+3] for i in range(max(1, len(value)-2))}

def aggregate(candidates: list[dict]) -> dict:
    buckets = defaultdict(list)
    for idea in candidates:
        buckets[structural_key(idea)].append(idea["id"])
    families = [{"id": f"family-{i+1:03d}", "members": members,
                 "relation": "exact_normalized_scientific_object_and_minimal_experiment"}
                for i, (_, members) in enumerate(sorted(buckets.items()))]
    possible = []
    for i, left in enumerate(candidates):
        lg = grams(left["mechanism"])
        for right in candidates[i+1:]:
            if structural_key(left) == structural_key(right):
                continue
            rg = grams(right["mechanism"])
            similarity = len(lg & rg) / max(1, len(lg | rg))
            if similarity >= .60:
                possible.append({"left": left["id"], "right": right["id"], "lexical_similarity": round(similarity, 3),
                                 "decision": "needs_human_or_evidence_aware_semantic_review"})
    return {"families": families, "possible_duplicates": possible, "raw_count": len(candidates),
            "family_count": len(families), "deletions": 0,
            "warning": "Shared provenance is not votes; no candidate was silently deleted."}
