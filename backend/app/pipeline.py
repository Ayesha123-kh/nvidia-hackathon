"""One run, as an async generator of SSE-ready events."""
import asyncio
import json
import statistics
from typing import AsyncIterator

from . import config, evidence, lenses, verifier
from .llm import LLM
from .schemas import (CriticReport, CustomerVote, IdeaCanvas, JudgeOutput,
                      RouterOutput, SegmentList, Verdict)

ROLES = {
    "skeptical_user": "Why a real customer would not bother.",
    "competitor": "What people use instead and where the idea loses.",
    "engineer": "Technical risk, hidden complexity, build cost.",
    "finance": "Pricing, market size, unit economics. If price is missing, treat pricing as unknown.",
}
CITE_RULE = "Every factual point must end with a citation like [S3] from the evidence pack, or be tagged ASSUMPTION."


def ev(kind: str, data) -> dict:
    return {"event": kind, "data": json.dumps(data, default=lambda o: o.model_dump())}


async def extract_canvas(llm: LLM, text: str) -> IdeaCanvas:
    return await llm.json_call("fast", "Extract an Idea Canvas. Leave unknown fields empty; never invent.", text, IdeaCanvas)


async def run(llm: LLM, canvas: IdeaCanvas) -> AsyncIterator[dict]:
    idea = canvas.model_dump_json()
    yield ev("canvas", {"canvas": canvas, "missing": canvas.missing_fields()})

    router = await llm.json_call(
        "fast", "Tag the domain (e.g. fintech, healthcare, food_delivery) and list 4-6 claims worth fact-checking "
        "(competitor pricing, regulation, market size, incumbent behaviour), each with a search query under 400 chars.",
        idea, RouterOutput)
    lens = lenses.load(router.domain)
    pack = await evidence.build_pack(router.claims)
    yield ev("evidence", {"domain": router.domain, "sources": pack})
    ctx = f"IDEA: {idea}\nKNOWN FAILURE MODES: {lens['failure_modes']}\nEVIDENCE:\n{evidence.render(pack)}"

    async def critic(role: str, job: str) -> CriticReport:
        r = await llm.json_call("fast", f"You are the {role} critic. {job} {CITE_RULE}", ctx, CriticReport)
        r.role = role  # type: ignore[assignment]
        return r

    seg = await llm.json_call("fast", "Create 8 customer segments: 2 early_adopter, 3 mainstream, 3 skeptical.", ctx, SegmentList)

    async def customer(i: int) -> CustomerVote:
        s = seg.segments[i % len(seg.segments)]
        return await llm.json_call(
            "fast", f"You are one independent customer #{i} in segment {s.kind}: {s.description}. State your objection "
            "first, a realistic budget, the existing tool you would have to drop, then vote pay/maybe/no. "
            "'maybe' requires exactly one named condition.", ctx, CustomerVote)

    critic_tasks = [asyncio.create_task(critic(r, j)) for r, j in ROLES.items()]
    cust_tasks = [asyncio.create_task(customer(i)) for i in range(config.N_CUSTOMERS)]
    reports: list[CriticReport] = []
    for fut in asyncio.as_completed(critic_tasks):
        r = await fut
        reports.append(r)
        yield ev("critic", r)
    votes: list[CustomerVote] = []
    for fut in asyncio.as_completed(cust_tasks):
        v = await fut
        votes.append(v)
        yield ev("customer", {"vote": v.vote, "objection": v.objection})

    cites = verifier.check_citations(reports, pack)
    tally = verifier.tally(votes)
    yield ev("verified", {"citations": cites, "tally": tally, "simulated": True})

    judge_ctx = ctx + f"\nCRITICS: {[r.model_dump() for r in reports]}\nCUSTOMER TALLY (computed in code): {tally}\n" \
                      f"EVIDENCE COVERAGE: {cites['coverage']:.2f}. If coverage is low, be less confident."
    judges: list[JudgeOutput] = await asyncio.gather(*[
        llm.json_call("ultra", "You are the judge. Score survival 0-100, pick top 3 fatal flaws, each with the "
                      "assumption that must be true and the cheapest experiment with a pass/kill metric, and "
                      "recommend BUILD, PIVOT or KILL.", judge_ctx, JudgeOutput)
        for _ in range(config.JUDGE_RUNS)])
    scores = [j.score for j in judges]
    mid = judges[scores.index(sorted(scores)[len(scores) // 2])]
    verdict = Verdict(score_median=int(statistics.median(scores)), score_min=min(scores), score_max=max(scores),
                      recommendation=mid.recommendation, flaws=mid.flaws,
                      evidence_coverage=cites["coverage"], tally=tally)
    yield ev("verdict", verdict)
    yield ev("done", {"stats": [s.__dict__ for s in llm.stats]})
