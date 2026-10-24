# Peperio: Entity Relationship Diagram and Data Flow

Peperio has **no accounts, saved history or payments** (out of scope). Entities below are the
Pydantic models that move through one run. They can be held in memory per run and
serialised to JSON for replay recordings and backtest results.

## ERD

```mermaid
erDiagram
    RUN ||--|| IDEA_CANVAS : "starts from"
    RUN ||--o{ CLAIM : "router extracts 4-6"
    CLAIM ||--o| EVIDENCE_SOURCE : "Tavily query returns S#"
    RUN }o--|| DOMAIN_LENS : "uses (YAML)"
    RUN ||--o{ CRITIC_REPORT : "4 critics"
    CRITIC_REPORT ||--o{ CITATION : "cites S# or ASSUMPTION"
    CITATION }o--|| EVIDENCE_SOURCE : "references"
    RUN ||--o{ SEGMENT : "8 customer types"
    SEGMENT ||--o{ SIM_CUSTOMER : "40 total"
    SIM_CUSTOMER ||--|| CUSTOMER_VOTE : "pay / maybe / no"
    RUN ||--o{ CLAIM_CHECK : "verifier"
    CLAIM_CHECK }o--|| CITATION : "checks"
    RUN ||--o{ JUDGE_RUN : "3 runs"
    JUDGE_RUN ||--o{ FLAW : "top 3"
    FLAW ||--|| EXPERIMENT : "cheapest test"
    RUN ||--|| VERDICT : "median + range"
    RUN ||--o{ RESURRECT_ROUND : "up to 3"
    RESURRECT_ROUND ||--|| IDEA_CANVAS : "rewritten"
    RUN ||--o{ LLM_CALL : "telemetry (HUD)"
    BACKTEST_SET ||--o{ BACKTEST_CASE : "16-20 + 4 controls"
    BACKTEST_CASE ||--o{ BACKTEST_RESULT : "per setup A/B/C"
    BACKTEST_RESULT }o--|| RUN : "produced by"
    REAL_USER_FEEDBACK }o--|| RUN : "rates"

    RUN {
        uuid id PK
        enum setup "A_single | B_single_evidence | C_peperio"
        enum status "running | done | failed"
        datetime started_at
        bool replay "recorded run"
    }
    IDEA_CANVAS {
        uuid id PK
        text target_user
        text problem
        text solution
        text price "nullable, flagged if missing"
        text riskiest_belief
        text market
        int round "0 = original"
    }
    CLAIM {
        int id PK
        text text
        text domain
        text query "under 400 chars"
    }
    EVIDENCE_SOURCE {
        string sid PK "S1..Sn"
        text title
        text url
        text snippet
        date published
    }
    DOMAIN_LENS {
        string key PK "fintech, healthcare, food_delivery, generic..."
        yaml failure_modes
    }
    CRITIC_REPORT {
        enum role "skeptical_user | competitor | engineer | finance"
        text body
    }
    CITATION {
        int id PK
        string ref "S# or ASSUMPTION"
        text claim_text
    }
    SEGMENT {
        int id PK
        enum kind "early_adopter | mainstream | skeptical"
        text description
    }
    SIM_CUSTOMER {
        int id PK
        text persona
        decimal budget
        text existing_tool_to_drop
    }
    CUSTOMER_VOTE {
        enum vote "pay | maybe | no"
        text objection "objection first"
        text maybe_condition "required if maybe"
    }
    CLAIM_CHECK {
        bool id_exists
        bool snippet_supports
        enum action "keep | flag | drop"
    }
    JUDGE_RUN {
        int run_no "1..3"
        int survival_score
        text rationale
    }
    FLAW {
        int rank "1..3"
        text description
        text must_be_true_assumption
    }
    EXPERIMENT {
        text test
        text cost
        text pass_kill_metric
    }
    VERDICT {
        int score_median
        int score_min
        int score_max
        enum recommendation "BUILD | PIVOT | KILL"
        float evidence_coverage
    }
    RESURRECT_ROUND {
        int round_no "1..3"
        bool new_facts_flag "code check"
        int new_median
        bool beats_old_max "gain counts only if true"
    }
    LLM_CALL {
        uuid id PK
        enum tier "fast_nemotron | ultra_nemotron"
        string model_id "from GET /v1/models"
        int tokens_in
        int tokens_out
        int latency_ms
        decimal cost_usd
    }
    BACKTEST_SET {
        string id PK
    }
    BACKTEST_CASE {
        string id PK
        text pitch_stage_description "names stripped"
        enum outcome "failed | survived | absurd_control"
    }
    BACKTEST_RESULT {
        string setup
        int score
        float pairwise_rank_accuracy
    }
    REAL_USER_FEEDBACK {
        int id PK
        int unseen_risk_1to5
        bool opened_source
    }
```

## Data flow (what moves where)

```mermaid
flowchart LR
    U[User pastes idea] --> N1[Nano: extract]
    N1 --> IC[(Idea Canvas<br/>editable)]
    IC --> RT[Nano: domain router<br/>+ 4-6 claims]
    RT --> TV[Tavily search<br/>1 query per claim, cached]
    TV --> EP[(Evidence pack S1..Sn)]
    RT --> LENS[(Domain lens YAML)]
    IC & EP & LENS --> CR[4 critics<br/>Fast Nemotron]
    IC & EP --> SEG[Segment maker<br/>8 types]
    SEG --> CU[40 independent customer calls<br/>Fast Nemotron]
    CU --> TALLY[Code: count pay / maybe / no]
    CR --> CV[Claim verifier<br/>code + Nano]
    EP --> CV
    CV --> COV[Evidence coverage meter]
    CR & TALLY & CV --> J[Ultra judge x3]
    J --> V[Verdict: median + range,<br/>3 flaws, experiments, BUILD/PIVOT/KILL]
    V --> RW[Rewriter Ultra<br/>no invented facts]
    RW --> NF{Code: new numbers<br/>or entities?}
    NF --> RE[Re-test, up to 3 rounds]
    RE --> GAIN{new median > old max?}
    GAIN -- yes --> OUT1[Reported gain]
    GAIN -- no --> OUT2["no reliable change"]
    V --> CARD[Cause-of-death card]
    LLM[(LLM_CALL telemetry)] --> HUD[Live HUD]
```
