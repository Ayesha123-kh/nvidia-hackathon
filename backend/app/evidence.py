"""Tavily evidence pack: 1 query per claim, cached, numbered [S1..Sn]."""
import httpx

from . import config
from .schemas import Claim, EvidenceSource

_cache: dict[str, list[dict]] = {}


async def search(query: str) -> list[dict]:
    if query in _cache:
        return _cache[query]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.tavily.com/search",
            json={"api_key": config.TAVILY_API_KEY, "query": query[:400], "max_results": 3},
        )
        r.raise_for_status()
    _cache[query] = r.json().get("results", [])
    return _cache[query]


async def build_pack(claims: list[Claim]) -> list[EvidenceSource]:
    pack: list[EvidenceSource] = []
    for claim in claims[: config.MAX_CLAIMS]:
        for hit in await search(claim.query):
            pack.append(
                EvidenceSource(
                    sid=f"S{len(pack) + 1}",
                    title=hit.get("title", ""),
                    url=hit.get("url", ""),
                    snippet=hit.get("content", "")[:500],
                    published=hit.get("published_date"),
                )
            )
    return pack


def render(pack: list[EvidenceSource]) -> str:
    return "\n".join(f"[{s.sid}] {s.title} ({s.url}): {s.snippet}" for s in pack) or "(no evidence found)"
