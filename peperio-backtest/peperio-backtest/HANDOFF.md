# Peperio backtest harness: handoff (Faisal's task)

Built against the real code on `main` of Ayesha123-kh/nvidia-hackathon (commit 4c74439).
The `faisal` branch only has the initial commit, so start your branch from `main`
(or merge `main` into `faisal` first).

## Files (copy these into the repo root, keeping the folder)

```
backtest/__init__.py      empty, makes "python -m backtest.harness" work
backtest/harness.py       the harness
backtest/cases.json       6 failed + 6 survived ventures (names stripped) + 4 absurd controls
backtest/test_harness.py  4 tests, no API keys needed
backtest/results/.gitkeep results land here
```
Also add this line to `.gitignore` so mock files never get committed:
```
backtest/results/MOCK_*
```
Or apply everything at once: `git checkout -b faisal-backtest main && git am backtest-harness.patch`

## Commands (run from the repo root, with the backend requirements installed)

```bash
pip install -r backend/requirements.txt

# 1. Tests, no keys needed
python -m pytest backtest/test_harness.py -q

# 2. Mock run, no API credits (checks wiring only, numbers are fake)
python -m backtest.harness --mode mock

# 3. Cheap live check: 1 failed, 1 survived, 1 absurd, small crowd
python -m backtest.harness --mode live --cases F01,S01,X01 --customers 8 --judge-runs 1

# 4. Full live run for the README table (default 40 customers, 3 judges)
python -m backtest.harness --mode live
```
Other flags: `--limit N`, `--setups A,C`, `--repeats 3` (stability), `--timeout 900`.
Live mode needs `TOKEN_FACTORY_API_KEY`, `TOKEN_FACTORY_BASE_URL` and `TAVILY_API_KEY` in `.env`.

## What it measures (per setup A, B, C)

| Column | Meaning |
|---|---|
| completion_rate | runs that reached a verdict / runs attempted |
| pairwise_rank_accuracy | share of (survived, failed) pairs where the survivor scored higher; ties = 0.5; 36 pairs; 0.5 = coin flip |
| absurd_rejection_rate | share of absurd controls given KILL |
| absurd_below_real_rate | share of (absurd, real) pairs where absurd scored lower |
| mean_evidence_coverage | verifier.check_citations coverage (C from the verdict, B from the single prompt's points, A has none) |
| mean_judge_range | C: score_max - score_min across the 3 judges |
| rec_BUILD / PIVOT / KILL | recommendation counts |
| llm_calls, tokens_in, tokens_out, model_latency_ms | from llm.stats, sliced per run |
| wall_ms | real time per run (model latency is summed per call, calls overlap) |

Outputs: `backtest/results/backtest_live_<time>.json` (meta + summary + every run),
`..._runs.csv` (one row per case x setup) and `..._summary.csv` (one row per setup).
Mock files start with `MOCK_` and have `"mock": true` in the JSON.

A full live run is about 16 cases x (1 + 2 + 49) = 832 LLM calls and up to 6 Tavily queries
per case for B and C (cached between them when queries match).

## Verified vs not verified

- Verified: 4 new tests pass, the 4 existing backend tests still pass, and the full mock run
  completes 48/48 runs through the real `pipeline.run` code (49 calls per C run, which matches
  router + segments + 4 critics + 40 customers + 3 judges).
- Not verified: live mode. There were no API keys here, so no call to Token Factory or Tavily was made.
  The first live run (command 3) is the real test.

## Message for the team leader

> Backtest harness is done and on branch `faisal-backtest` (from main). It runs our 16 cases
> (6 failed, 6 survived, 4 absurd controls, names stripped) through setup A (single prompt),
> B (single prompt + Tavily evidence) and C (full Peperio pipeline), and reports per setup:
> pairwise rank accuracy, absurd-control KILL rate, completion rate, evidence coverage, judge
> score range, BUILD/PIVOT/KILL counts, and tokens/latency from llm.stats. One failing case is
> logged and the run continues. Results go to backtest/results/ as JSON and CSV for Saad's page
> and the README table. Tests and a mock run pass with no API keys; mock numbers are fake and
> clearly labelled. I need the Token Factory and Tavily keys (or Ashi to run it) for the live
> run: about 830 LLM calls for the full set. Two questions below.

## Team must confirm

1. Setup A and B prompts. Ashi's baseline toggle is not in the repo yet, so the harness has its own
   single-prompt baseline in `harness.py` (`SINGLE_PROMPT`, Ultra tier). If Ashi writes a different
   one, swap it in so the app and the backtest use the same baseline.
2. Case list. README says 16-20 ventures + 4 controls; TRACKER says 12. The file has 12 + 4.
   Zarlishta should check the descriptions and add more if you want 16-20.
3. "Rejected" means the absurd control got KILL. Say if you want a score threshold instead.
4. Credits: is the full live run (~830 calls, plus `--repeats` if you want stability) affordable?
   Run command 3 first to see the token cost of 3 cases.
5. Famous cases (Airbnb, Theranos, Quibi...) may be recognised by the model even with names stripped.
   The README already says this is a sanity check, not proof; keep that wording.
