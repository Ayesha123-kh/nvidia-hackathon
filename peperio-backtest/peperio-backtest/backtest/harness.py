"""Peperio backtest: run known-outcome ventures through setups A, B and C and score them.

Setups (same idea, same Token Factory models, so differences come from architecture):
  A  single prompt: one call plays critics, customers and judge
  B  single prompt + the same kind of Tavily evidence pack (router + evidence.build_pack)
  C  Peperio: the full pipeline.run event stream

Run from the repository root:
  python -m backtest.harness --mode mock                    # offline, no API credits
  python -m backtest.harness --mode live --limit 3          # first 3 cases, real APIs
  python -m backtest.harness --mode live                    # full set, for the README table

Mock mode drives the real pipeline code with a fake LLM and fake search results. It checks
the harness and the pipeline wiring only. Its numbers are noise and must never be reported.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import random
import statistics
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from pydantic import BaseModel, Field  # noqa: E402

from app import config, evidence, pipeline, verifier  # noqa: E402
from app.llm import LLM, CallStat  # noqa: E402
from app.schemas import (CriticReport, CustomerVote, Flaw, IdeaCanvas, JudgeOutput,  # noqa: E402
                         RouterOutput, SegmentList)

CASES_FILE = Path(__file__).resolve().parent / "cases.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
SETUPS = ("A", "B", "C")
SETUP_NAMES = {"A": "A_single", "B": "B_single_evidence", "C": "C_peperio"}
OUTCOMES = ("failed", "survived", "absurd_control")


class SinglePromptOutput(BaseModel):
    """Setup A/B reply. Its tally is model-claimed, unlike C where counts are computed in code."""
    critic_points: list[str]
    customers_pay: int = Field(ge=0)
    customers_maybe: int = Field(ge=0)
    customers_no: int = Field(ge=0)
    score: int = Field(ge=0, le=100)
    flaws: list[Flaw] = Field(max_length=3)
    recommendation: Literal["BUILD", "PIVOT", "KILL"]
    rationale: str


SINGLE_PROMPT = (
    "Act as four critics (skeptical user, competitor, engineer, finance) and then as {n} independent customers "
    "who each vote pay, maybe or no. Then act as the judge: score survival 0-100, pick the top 3 fatal flaws, "
    "each with the assumption that must be true and the cheapest experiment with a pass/kill metric, and "
    "recommend BUILD, PIVOT or KILL."
)


# ---------------------------------------------------------------- cases

@dataclass
class Case:
    id: str
    outcome: str
    canvas: IdeaCanvas
    source: str = ""


def load_cases(path: Path = CASES_FILE) -> list[Case]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for c in raw["cases"]:
        if c["outcome"] not in OUTCOMES:
            raise ValueError(f"{c['id']}: outcome must be one of {OUTCOMES}, got {c['outcome']!r}")
        cases.append(Case(c["id"], c["outcome"], IdeaCanvas(**c["canvas"]), c.get("source", "")))
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("duplicate case ids in cases.json")
    return cases


# ---------------------------------------------------------------- setups

def _router_call(llm, idea: str):
    return llm.json_call(
        "fast", "Tag the domain (e.g. fintech, healthcare, food_delivery) and list 4-6 claims worth fact-checking "
        "(competitor pricing, regulation, market size, incumbent behaviour), each with a search query under 400 chars.",
        idea, RouterOutput)


async def run_single(llm, canvas: IdeaCanvas, with_evidence: bool) -> dict:
    idea = canvas.model_dump_json()
    system = SINGLE_PROMPT.format(n=config.N_CUSTOMERS)
    user, pack = f"IDEA: {idea}", []
    if with_evidence:
        router = await _router_call(llm, idea)
        pack = await evidence.build_pack(router.claims)
        system += " " + pipeline.CITE_RULE
        user += f"\nEVIDENCE:\n{evidence.render(pack)}"
    out = await llm.json_call("ultra", system, user, SinglePromptOutput)
    cites = verifier.check_citations([CriticReport(role="skeptical_user", points=out.critic_points)], pack) \
        if with_evidence else None
    return {
        "score": out.score, "score_min": out.score, "score_max": out.score,
        "recommendation": out.recommendation,
        "evidence_coverage": cites["coverage"] if cites else None,
        "citations": cites, "n_sources": len(pack),
        "tally": {"pay": out.customers_pay, "maybe": out.customers_maybe, "no": out.customers_no},
        "tally_source": "model_claimed",
        "flaws": [f.description for f in out.flaws],
    }


async def run_peperio(llm, canvas: IdeaCanvas) -> dict:
    res: dict = {"tally_source": "code", "events": {}}
    async for e in pipeline.run(llm, canvas):
        kind = e["event"]
        res["events"][kind] = res["events"].get(kind, 0) + 1
        data = json.loads(e["data"])
        if kind == "evidence":
            res["domain"], res["n_sources"] = data["domain"], len(data["sources"])
        elif kind == "verified":
            res["citations"] = data["citations"]
        elif kind == "verdict":
            res.update(score=data["score_median"], score_min=data["score_min"], score_max=data["score_max"],
                       recommendation=data["recommendation"], evidence_coverage=data["evidence_coverage"],
                       tally=data["tally"], flaws=[f["description"] for f in data["flaws"]])
    if "score" not in res:
        raise RuntimeError(f"pipeline ended without a verdict event; got {res['events']}")
    return res


async def run_setup(llm, setup: str, canvas: IdeaCanvas) -> dict:
    if setup == "A":
        return await run_single(llm, canvas, with_evidence=False)
    if setup == "B":
        return await run_single(llm, canvas, with_evidence=True)
    return await run_peperio(llm, canvas)


def usage(stats: list) -> dict:
    tiers: dict = {}
    for s in stats:
        t = tiers.setdefault(s.tier, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "latency_ms": 0})
        t["calls"] += 1
        t["tokens_in"] += s.tokens_in
        t["tokens_out"] += s.tokens_out
        t["latency_ms"] += s.latency_ms
    return {"calls": len(stats), "tokens_in": sum(s.tokens_in for s in stats),
            "tokens_out": sum(s.tokens_out for s in stats),
            "model_latency_ms": sum(s.latency_ms for s in stats),  # summed per call; calls overlap
            "models": sorted({s.model for s in stats}), "by_tier": tiers}


async def run_one(llm, case: Case, setup: str, repeat: int, timeout: float) -> dict:
    """One case x setup. Never raises: a failure is recorded and the run continues."""
    row = {"case_id": case.id, "outcome": case.outcome, "setup": SETUP_NAMES[setup], "repeat": repeat,
           "status": "done", "error": None}
    start, t0 = len(llm.stats), time.perf_counter()
    try:
        row.update(await asyncio.wait_for(run_setup(llm, setup, case.canvas), timeout))
    except Exception as e:  # noqa: BLE001 - one bad case must not stop the backtest
        row.update(status="failed", error=f"{type(e).__name__}: {e}"[:500],
                   traceback=traceback.format_exc(limit=3)[-1500:])
    row["wall_ms"] = int((time.perf_counter() - t0) * 1000)
    row["usage"] = usage(llm.stats[start:])
    return row


# ---------------------------------------------------------------- metrics

def pairwise_rank_accuracy(scores: dict[str, float], outcomes: dict[str, str]) -> tuple[Optional[float], int]:
    """Share of (survived, failed) pairs where the survivor scored higher. Ties count half."""
    surv = [scores[c] for c in scores if outcomes[c] == "survived"]
    fail = [scores[c] for c in scores if outcomes[c] == "failed"]
    pairs = [(s, f) for s, f in product(surv, fail)]
    if not pairs:
        return None, 0
    return sum(1.0 if s > f else 0.5 if s == f else 0.0 for s, f in pairs) / len(pairs), len(pairs)


def _mean(xs: list) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 4) if xs else None


def summarise(rows: list[dict]) -> list[dict]:
    out = []
    for name in dict.fromkeys(r["setup"] for r in rows):
        rs = [r for r in rows if r["setup"] == name]
        ok = [r for r in rs if r["status"] == "done"]
        outcomes = {r["case_id"]: r["outcome"] for r in rs}
        by_case: dict[str, list[int]] = {}
        for r in ok:
            by_case.setdefault(r["case_id"], []).append(r["score"])
        case_score = {c: statistics.median(v) for c, v in by_case.items()}  # median over repeats
        acc, n_pairs = pairwise_rank_accuracy(case_score, outcomes)
        real = [c for c in case_score if outcomes[c] != "absurd_control"]
        absurd_rows = [r for r in ok if r["outcome"] == "absurd_control"]
        absurd = [c for c in case_score if outcomes[c] == "absurd_control"]
        below = [case_score[a] < case_score[r] for a in absurd for r in real]
        recs = {k: sum(r["recommendation"] == k for r in ok) for k in ("BUILD", "PIVOT", "KILL")}
        spreads = [max(v) - min(v) for v in by_case.values() if len(v) > 1]
        u = [r["usage"] for r in rs]
        out.append({
            "setup": name,
            "runs": len(rs), "completed": len(ok), "completion_rate": round(len(ok) / len(rs), 4) if rs else None,
            "cases_scored": len(case_score),
            "mean_score_all": _mean(list(case_score.values())),
            "mean_score_survived": _mean([case_score[c] for c in real if outcomes[c] == "survived"]),
            "mean_score_failed": _mean([case_score[c] for c in real if outcomes[c] == "failed"]),
            "mean_score_absurd": _mean([case_score[c] for c in absurd]),
            "pairwise_rank_accuracy": round(acc, 4) if acc is not None else None, "pairs": n_pairs,
            "absurd_rejection_rate": round(sum(r["recommendation"] == "KILL" for r in absurd_rows)
                                           / len(absurd_rows), 4) if absurd_rows else None,
            "absurd_build_count": sum(r["recommendation"] == "BUILD" for r in absurd_rows),
            "absurd_below_real_rate": round(sum(below) / len(below), 4) if below else None,
            "mean_evidence_coverage": _mean([r.get("evidence_coverage") for r in ok]),
            "mean_judge_range": _mean([r["score_max"] - r["score_min"] for r in ok]),
            "mean_repeat_spread": _mean(spreads),
            "rec_BUILD": recs["BUILD"], "rec_PIVOT": recs["PIVOT"], "rec_KILL": recs["KILL"],
            "llm_calls": sum(x["calls"] for x in u),
            "tokens_in": sum(x["tokens_in"] for x in u), "tokens_out": sum(x["tokens_out"] for x in u),
            "model_latency_ms": sum(x["model_latency_ms"] for x in u),
            "wall_ms": sum(r["wall_ms"] for r in rs),
        })
    return out


# ---------------------------------------------------------------- mock mode

class MockLLM:
    """Stands in for app.llm.LLM: same json_call signature, fake but schema-valid replies, fake stats."""

    def __init__(self, seed: int = 0):
        self.seed, self.n = seed, 0
        self.stats: list[CallStat] = []
        self.fast_model, self.ultra_model = "MOCK-fast", "MOCK-ultra"

    async def json_call(self, tier, system, user, schema, retries=1):
        self.n += 1
        h = hashlib.sha256(f"{self.seed}|{self.n}|{system}|{user}".encode()).hexdigest()
        rng = random.Random(int(h[:16], 16))
        await asyncio.sleep(0)
        self.stats.append(CallStat(tier, self.ultra_model if tier == "ultra" else self.fast_model,
                                   (len(system) + len(user)) // 4, rng.randint(80, 600), rng.randint(5, 40)))
        return schema.model_validate(self._fake(schema, rng, user))

    @staticmethod
    def _fake(schema, rng: random.Random, user: str) -> dict:
        sids = sorted(set(pipeline.verifier._CITE.findall(user)))
        def point(i):
            pick = rng.random()
            if sids and pick < 0.6:
                return f"Mock point {i} [{rng.choice(sids)}]"
            return f"Mock point {i} ASSUMPTION" if pick < 0.85 else f"Mock point {i} [S999]"
        def flaws():
            return [{"description": f"Mock flaw {i}", "must_be_true": "x", "experiment": "y",
                     "experiment_cost": "$0", "pass_kill_metric": "z"} for i in range(3)]
        score = rng.randint(0, 100)
        rec = "BUILD" if score >= 65 else "PIVOT" if score >= 35 else "KILL"
        if schema is IdeaCanvas:
            return {"target_user": "mock", "problem": "mock", "solution": "mock"}
        if schema is RouterOutput:
            dom = rng.choice(["fintech", "healthcare", "food_delivery", "generic"])
            return {"domain": dom, "claims": [{"id": i, "text": f"claim {i}", "query": f"mock query {i}"}
                                              for i in range(rng.randint(4, 6))]}
        if schema is SegmentList:
            kinds = ["early_adopter"] * 2 + ["mainstream"] * 3 + ["skeptical"] * 3
            return {"segments": [{"kind": k, "description": f"mock {k}"} for k in kinds]}
        if schema is CriticReport:
            return {"role": "engineer", "points": [point(i) for i in range(4)]}
        if schema is CustomerVote:
            vote = rng.choice(["pay", "maybe", "no"])
            return {"objection": "mock", "budget": rng.randint(0, 50), "tool_to_drop": "mock", "vote": vote,
                    "maybe_condition": "mock" if vote == "maybe" else None}
        if schema is JudgeOutput:
            return {"score": score, "flaws": flaws(), "recommendation": rec, "rationale": "mock"}
        if schema is SinglePromptOutput:
            pay = rng.randint(0, config.N_CUSTOMERS)
            maybe = rng.randint(0, config.N_CUSTOMERS - pay)
            return {"critic_points": [point(i) for i in range(8)], "customers_pay": pay, "customers_maybe": maybe,
                    "customers_no": config.N_CUSTOMERS - pay - maybe, "score": score, "flaws": flaws(),
                    "recommendation": rec, "rationale": "mock"}
        raise TypeError(f"MockLLM has no fake for {schema.__name__}")


async def _mock_search(query: str) -> list[dict]:
    return [{"title": f"Mock source for {query[:40]}", "url": "https://example.invalid/mock",
             "content": "Mock snippet. Not real evidence.", "published_date": None} for _ in range(2)]


# ---------------------------------------------------------------- reporting

def write_results(rows: list[dict], summary: list[dict], meta: dict) -> dict[str, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{'MOCK_' if meta['mode'] == 'mock' else ''}backtest_{meta['mode']}_{meta['run_id']}"
    paths = {"json": RESULTS_DIR / f"{stem}.json", "runs_csv": RESULTS_DIR / f"{stem}_runs.csv",
             "summary_csv": RESULTS_DIR / f"{stem}_summary.csv"}
    paths["json"].write_text(json.dumps({"meta": meta, "summary": summary, "runs": rows}, indent=2), encoding="utf-8")
    run_cols = ["case_id", "outcome", "setup", "repeat", "status", "score", "score_min", "score_max",
                "recommendation", "evidence_coverage", "n_sources", "tally_pay", "tally_maybe", "tally_no",
                "tally_source", "llm_calls", "tokens_in", "tokens_out", "model_latency_ms", "wall_ms", "error"]
    with paths["runs_csv"].open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=run_cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            t, u = r.get("tally") or {}, r["usage"]
            w.writerow({**r, "tally_pay": t.get("pay"), "tally_maybe": t.get("maybe"), "tally_no": t.get("no"),
                        "llm_calls": u["calls"], "tokens_in": u["tokens_in"], "tokens_out": u["tokens_out"],
                        "model_latency_ms": u["model_latency_ms"]})
    with paths["summary_csv"].open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]) if summary else ["setup"])
        w.writeheader()
        w.writerows(summary)
    return paths


def print_summary(summary: list[dict], mock: bool) -> None:
    if mock:
        print("\n*** MOCK RUN: fake LLM and fake evidence. These numbers are noise. Do not report them. ***")
    cols = [("setup", 18), ("completed", 9), ("pairwise_rank_accuracy", 8), ("absurd_rejection_rate", 8),
            ("mean_evidence_coverage", 8), ("mean_score_survived", 8), ("mean_score_failed", 8),
            ("rec_BUILD", 5), ("rec_PIVOT", 5), ("rec_KILL", 5), ("tokens_in", 9), ("tokens_out", 9)]
    heads = ["setup", "done", "pairAcc", "absKILL", "evCov", "survAvg", "failAvg", "BUILD", "PIVOT", "KILL",
             "tok_in", "tok_out"]
    print("  ".join(h.ljust(w) for h, (_, w) in zip(heads, cols)))
    for s in summary:
        cells = []
        for k, w in cols:
            v = s[k]
            v = f"{s['completed']}/{s['runs']}" if k == "completed" else "-" if v is None else \
                f"{v:.2f}" if isinstance(v, float) else str(v)
            cells.append(v.ljust(w))
        print("  ".join(cells))


# ---------------------------------------------------------------- main

async def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["mock", "live"], required=True)
    p.add_argument("--limit", type=int, help="only the first N cases (cheap live check)")
    p.add_argument("--cases", help="comma-separated case ids, e.g. F01,S01,X01")
    p.add_argument("--setups", default="A,B,C", help="subset of A,B,C (default all)")
    p.add_argument("--repeats", type=int, default=1, help="runs per case per setup (stability)")
    p.add_argument("--customers", type=int, help=f"override N_CUSTOMERS (default {config.N_CUSTOMERS})")
    p.add_argument("--judge-runs", type=int, help=f"override JUDGE_RUNS (default {config.JUDGE_RUNS})")
    p.add_argument("--timeout", type=float, default=900, help="seconds per case per setup")
    p.add_argument("--cases-file", default=str(CASES_FILE))
    a = p.parse_args(argv)

    setups = [s.strip().upper() for s in a.setups.split(",") if s.strip()]
    if bad := [s for s in setups if s not in SETUPS]:
        p.error(f"unknown setups {bad}; use A, B, C")
    if a.customers:
        config.N_CUSTOMERS = a.customers  # pipeline reads config.N_CUSTOMERS at run time
    if a.judge_runs:
        config.JUDGE_RUNS = a.judge_runs
    cases = load_cases(Path(a.cases_file))
    if a.cases:
        wanted = {c.strip() for c in a.cases.split(",")}
        cases = [c for c in cases if c.id in wanted]
    if a.limit:
        cases = cases[: a.limit]
    if not cases:
        p.error("no cases selected")

    if a.mode == "mock":
        llm = MockLLM()
        evidence.search = _mock_search  # build_pack looks this up at call time
    else:
        missing = [k for k in ("TOKEN_FACTORY_API_KEY", "TOKEN_FACTORY_BASE_URL", "TAVILY_API_KEY")
                   if not getattr(config, k)]
        if missing:
            print(f"Missing in .env: {', '.join(missing)}. Live mode needs them.", file=sys.stderr)
            return 2
        llm = await LLM.create()

    meta = {
        "mode": a.mode, "mock": a.mode == "mock",
        "warning": "MOCK RUN: fake LLM and fake evidence; not real results" if a.mode == "mock" else None,
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "fast_model": llm.fast_model, "ultra_model": llm.ultra_model,
        "n_customers": config.N_CUSTOMERS, "judge_runs": config.JUDGE_RUNS, "repeats": a.repeats,
        "setups": [SETUP_NAMES[s] for s in setups], "cases": [c.id for c in cases],
        "full_config": not (a.customers or a.judge_runs or a.limit or a.cases),
    }
    print(f"{a.mode.upper()} backtest: {len(cases)} cases x {setups} x {a.repeats} repeat(s); "
          f"models fast={llm.fast_model} ultra={llm.ultra_model}")

    rows: list[dict] = []
    for case in cases:  # sequential so llm.stats slices belong to one run
        for setup in setups:
            for rep in range(a.repeats):
                row = await run_one(llm, case, setup, rep, a.timeout)
                rows.append(row)
                msg = (f"score={row['score']} rec={row['recommendation']}" if row["status"] == "done"
                       else f"FAILED {row['error']}")
                print(f"  {case.id:<4} {case.outcome:<15} {SETUP_NAMES[setup]:<18} #{rep} {msg} "
                      f"({row['wall_ms'] / 1000:.1f}s, {row['usage']['calls']} calls)")

    meta["finished_at"] = datetime.now(timezone.utc).isoformat()
    meta["usage_total"] = usage(llm.stats)
    summary = summarise(rows)
    paths = write_results(rows, summary, meta)
    print_summary(summary, a.mode == "mock")
    print("\nWrote:\n" + "\n".join(f"  {p_}" for p_ in paths.values()))
    return 0 if any(r["status"] == "done" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
