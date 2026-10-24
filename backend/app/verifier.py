"""Code-only checks. Counts and citation IDs are never model-generated."""
import re
from collections import Counter

from .schemas import CriticReport, CustomerVote, EvidenceSource

_CITE = re.compile(r"\[(S\d+)\]")


def tally(votes: list[CustomerVote]) -> dict[str, int]:
    c = Counter(v.vote for v in votes)
    return {k: c.get(k, 0) for k in ("pay", "maybe", "no")}


def check_citations(reports: list[CriticReport], pack: list[EvidenceSource]) -> dict:
    """A point is grounded if it cites an existing [S#]; ASSUMPTION is allowed but not grounded."""
    valid = {s.sid for s in pack}
    grounded = assumption = bad = 0
    for r in reports:
        for p in r.points:
            ids = _CITE.findall(p)
            if ids and all(i in valid for i in ids):
                grounded += 1
            elif "ASSUMPTION" in p and not ids:
                assumption += 1
            else:
                bad += 1  # missing or non-existent citation: drop or flag
    total = grounded + assumption + bad
    return {"grounded": grounded, "assumption": assumption, "invalid": bad,
            "coverage": grounded / total if total else 0.0}


def new_facts(original: str, evidence: str, rewritten: str) -> list[str]:
    """Numbers or Capitalised entities in the rewrite that appear in neither source."""
    allowed = (original + " " + evidence).lower()
    tokens = re.findall(r"\$?\d[\d,.]*%?|\b[A-Z][a-zA-Z]{2,}\b", rewritten)
    return sorted({t for t in tokens if t.lower() not in allowed})


def gain_is_real(old_scores: list[int], new_scores: list[int]) -> bool:
    """Noise floor: report a gain only if the new median beats the old maximum."""
    new_med = sorted(new_scores)[len(new_scores) // 2]
    return new_med > max(old_scores)
