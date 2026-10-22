from app import verifier
from app.schemas import CriticReport, CustomerVote, EvidenceSource

PACK = [EvidenceSource(sid="S1", title="t", url="u", snippet="s")]


def v(vote):
    return CustomerVote(objection="o", budget=5, tool_to_drop="x", vote=vote)


def test_tally_counts_in_code():
    assert verifier.tally([v("pay"), v("no"), v("no"), v("maybe")]) == {"pay": 1, "maybe": 1, "no": 2}


def test_citation_check():
    r = CriticReport(role="engineer", points=["a [S1]", "b ASSUMPTION", "c [S9]", "d"])
    out = verifier.check_citations([r], PACK)
    assert (out["grounded"], out["assumption"], out["invalid"]) == (1, 1, 2)


def test_noise_floor():
    assert not verifier.gain_is_real([60, 70, 65], [66, 68, 64])
    assert verifier.gain_is_real([60, 62, 61], [70, 72, 71])


def test_new_facts_flagged():
    assert "$99" in verifier.new_facts("meal kits for gyms", "", "Meal kits for gyms at $99")
