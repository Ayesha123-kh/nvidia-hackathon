# Progress tracker (compressed: project ready by Oct 24)

Source of truth: GitHub Issues (label `task`, `day-*`, `owner-*`). Tick items here when the issue closes.
Hard hackathon deadline is Oct 30, 22:00 PKT; Oct 25-30 is buffer for fixes, video and submission only.

| Owner | Area |
|-------|------|
| Ashi | Pipeline, evidence, verifier, deploy |
| Faisal | Backtest harness and metrics |
| Saad | UI, HUD, score-range chart, backtest page |
| Zarlishta | Domain lenses, example ideas, README |
| Danyal | Test matrix, real users, video, submission |

## Oct 22 (today): backend core
- [x] Repo, MIT, README, ERD, architecture docs
- [x] Backend scaffold: schemas, Token Factory client, Tavily client, verifier, pipeline, SSE API (`backend/`)
- [ ] Keys in `.env`; run once end to end against real Token Factory; confirm `/v1/models` tier picks and rate-limit headers (Ashi)
- [ ] Streamlit UI skeleton: paste box, Idea Canvas, live critics/customers (Saad)
- [ ] Lenses: fintech, healthcare, food_delivery, generic (done); example ideas (Zarlishta)
- [ ] Backtest cases: 12 ventures + absurd controls (Faisal, Zarlishta)

## Oct 23: complete the app
- [ ] Baseline setups A (single prompt) and C (pipeline) toggle (Ashi)
- [ ] Resurrect (1 round, noise floor via `verifier.gain_is_real`) (Ashi)
- [ ] HUD + score-range chart + verdict/experiments view (Saad)
- [ ] Backtest harness and results (Faisal)
- [ ] Deploy to Nebius Serverless Endpoint (Ashi)

## Oct 24: project ready
- [ ] Replay mode with 3 recorded runs (Ashi)
- [ ] Backtest results page + README results table filled from real runs (Saad, Zarlishta)
- [ ] 3-5 real-user tests (Danyal)
- [ ] Stranger test of the public URL in a private window

## Oct 25-29: buffer
- [ ] Video (<3 min, public YouTube), README final, feedback-notes.md, submit by Oct 29 (Danyal)
