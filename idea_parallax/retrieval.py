"""Optional Crossref metadata retrieval. Metadata does not verify a paper's claims."""
from __future__ import annotations
from urllib.parse import urlencode
import asyncio
from .providers import request_json
from .io_utils import digest

async def search_crossref(query: str, limit: int = 5) -> dict:
    query = query[:500]
    url = "https://api.crossref.org/works?" + urlencode({"query.bibliographic": query, "rows": limit})
    raw = await asyncio.to_thread(request_json, url, timeout=20)
    items = raw.get("message", {}).get("items", [])
    records = []
    for item in items:
        doi = item.get("DOI", "")
        title = item.get("title", [])
        if not isinstance(doi, str) or not isinstance(title, list) or not title or not isinstance(title[0], str):
            continue
        records.append({"id": "crossref-"+digest(doi.casefold())[:16], "title": title[0][:20000],
                        "url": "https://doi.org/"+doi, "doi": doi,
                        "excerpt": "", "status": "retrieved_metadata_only"})
    return {"query": query, "source": "crossref", "records": records, "status": "metadata_only",
            "warning": "No full text was read. Zero results do not establish novelty."}
