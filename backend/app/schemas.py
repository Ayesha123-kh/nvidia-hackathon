from typing import Literal, Optional

from pydantic import BaseModel, Field


class IdeaCanvas(BaseModel):
    target_user: str = ""
    problem: str = ""
    solution: str = ""
    price: Optional[str] = None
    riskiest_belief: str = ""
    market: str = ""

    def missing_fields(self) -> list[str]:
        return [k for k, v in self.model_dump().items() if not v]


class Claim(BaseModel):
    id: int
    text: str
    query: str = Field(max_length=400)


class RouterOutput(BaseModel):
    domain: str
    claims: list[Claim] = Field(max_length=6)


class EvidenceSource(BaseModel):
    sid: str  # S1..Sn
    title: str
    url: str
    snippet: str
    published: Optional[str] = None


class CriticReport(BaseModel):
    role: Literal["skeptical_user", "competitor", "engineer", "finance"]
    points: list[str]  # each point ends with [S#] or ASSUMPTION


class Segment(BaseModel):
    kind: Literal["early_adopter", "mainstream", "skeptical"]
    description: str


class SegmentList(BaseModel):
    segments: list[Segment]


class CustomerVote(BaseModel):
    objection: str  # objection first
    budget: float
    tool_to_drop: str
    vote: Literal["pay", "maybe", "no"]
    maybe_condition: Optional[str] = None


class Flaw(BaseModel):
    description: str
    must_be_true: str
    experiment: str
    experiment_cost: str
    pass_kill_metric: str


class JudgeOutput(BaseModel):
    score: int = Field(ge=0, le=100)
    flaws: list[Flaw] = Field(max_length=3)
    recommendation: Literal["BUILD", "PIVOT", "KILL"]
    rationale: str


class Verdict(BaseModel):
    score_median: int
    score_min: int
    score_max: int
    recommendation: str
    flaws: list[Flaw]
    evidence_coverage: float
    tally: dict[str, int]
