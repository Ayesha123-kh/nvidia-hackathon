# Peperio: System Architecture and Workflow

## Components

```mermaid
flowchart TB
    subgraph Client["Browser: Next.js (Streamlit fallback)"]
        UI1[Paste box]
        UI2[Idea Canvas editor]
        UI3[Debate view: 4 critic cards + 40 customer dots]
        UI4[Verdict + experiments + Resurrect]
        UI5[HUD: tokens, latency, $ per tier]
        UI6[Baseline toggle A / B / C]
        UI7[Backtest results page]
        UI8[Cause-of-death card export]
    end

    subgraph API["Python FastAPI on Nebius Serverless Endpoint"]
        EP1["/run  (SSE stream)"]
        EP2["/backtest"]
        EP3["/replay"]
        RL[Per-visitor rate limiter]
        ORCH[Pipeline orchestrator]
        subgraph Agents
            A1[Router / extractor: Nano]
            A2[4 critics: Fast Nemotron]
            A3[Segment maker + 40 customers: Fast]
            A4[Claim verifier]
            A5[Judge x3: Ultra]
            A6[Rewriter: Ultra]
        end
        CODE["Code-only checks:<br/>vote tally, citation ID check,<br/>noise floor, new-fact flag"]
        LENSES[(lenses/*.yaml)]
        CACHE[(Tavily cache)]
        REC[(recordings/*.json<br/>3 replay runs)]
        TEL[Telemetry collector]
        SCHEMA[Pydantic schemas<br/>enforced JSON output]
    end

    subgraph External
        TF["Nebius Token Factory<br/>OpenAI SDK, /v1/models at startup"]
        TAV[Tavily API]
    end

    Client -- HTTPS + SSE --> RL --> EP1 & EP2 & EP3
    EP1 --> ORCH --> Agents
    ORCH --> CODE
    Agents --> SCHEMA
    Agents -- NVIDIA Nemotron models --> TF
    ORCH -- evidence queries --> CACHE --> TAV
    ORCH --> LENSES
    Agents --> TEL --> EP1
    EP3 --> REC
```

## Workflow (one run)

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as FastAPI
    participant TF as Token Factory (Nemotron)
    participant TV as Tavily

    User->>UI: Paste idea
    UI->>API: POST /run
    API->>TF: Nano: extract Idea Canvas
    TF-->>UI: Canvas (user edits, missing fields flagged)
    User->>UI: Confirm canvas
    API->>TF: Nano: tag domain + 4-6 claims
    API->>TV: 1 query per claim (max 6, cached)
    TV-->>API: Evidence pack S1..Sn
    par Debate (streamed via SSE)
        API->>TF: 4 critics (must cite S# or ASSUMPTION)
        API->>TF: Segment maker then 40 independent customers
    end
    API->>API: Verify cited IDs, tally votes in code
    API->>TF: Nano: does snippet support claim?
    API->>TF: Ultra judge x3 (schema constrained)
    API-->>UI: Verdict: median + range, 3 flaws, experiments, BUILD/PIVOT/KILL
    User->>UI: Click Resurrect
    API->>TF: Ultra rewriter (no new facts)
    API->>API: Flag new numbers/entities
    API->>TF: Re-test (up to 3 rounds)
    API-->>UI: Gain only if new median > old max, else "no reliable change"
```

## Design decisions

| Decision | Why |
|----------|-----|
| Tavily before critics | Claims are checkable; this is what a chat cannot do |
| 40 separate customer calls | Independence; one call writing 40 personas collapses into clones. Micro-batching only as a labelled fallback |
| Judge runs 3 times | Report a range, not one lucky number |
| Counts in code | Pay / maybe / no counts are never model-generated |
| Domain lens as YAML | Add a domain by adding data, not code |
| Model IDs from `GET /v1/models` | The dossier's IDs are unverified |
| Rate limits read from response headers | The 60 RPM figure is unverified |
| Replay mode | Keeps the demo alive if credits run out |

## Planned repo layout

```
backend/        FastAPI app, agents, pipeline, schemas, verifier
backend/lenses/ domain lens YAML files (10 + generic)
frontend/       Next.js UI (Streamlit fallback)
backtest/       harness, cases, metrics
recordings/     3 saved full runs for replay mode
docs/           ERD, architecture
```
