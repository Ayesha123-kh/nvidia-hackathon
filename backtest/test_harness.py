import asyncio
import json

from backtest import harness


def test_cases_file_shape():
    cases = harness.load_cases()
    outcomes = [c.outcome for c in cases]
    assert outcomes.count("failed") == 6 and outcomes.count("survived") == 6
    assert outcomes.count("absurd_control") == 4


def test_pairwise_rank_accuracy():
    outcomes = {"s1": "survived", "s2": "survived", "f1": "failed", "x": "absurd_control"}
    acc, n = harness.pairwise_rank_accuracy({"s1": 80, "s2": 40, "f1": 40, "x": 99}, outcomes)
    assert n == 2 and acc == 0.75  # s1>f1 counts 1, s2==f1 counts 0.5


def test_mock_run_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "RESULTS_DIR", tmp_path)
    assert asyncio.run(harness.main(["--mode", "mock", "--cases", "F01,S01,X01", "--customers", "5"])) == 0
    files = sorted(p.name for p in tmp_path.iterdir())
    assert len(files) == 3 and all(f.startswith("MOCK_") for f in files)
    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert data["meta"]["mock"] is True
    assert {s["setup"] for s in data["summary"]} == {"A_single", "B_single_evidence", "C_peperio"}
    assert all(r["status"] == "done" for r in data["runs"])
    c = [r for r in data["runs"] if r["setup"] == "C_peperio"][0]
    assert c["events"]["customer"] == 5 and c["events"]["verdict"] == 1
    assert sum(c["tally"].values()) == 5


def test_failure_is_recorded_not_raised():
    class Broken(harness.MockLLM):
        async def json_call(self, *a, **k):
            raise RuntimeError("boom")
    case = harness.load_cases()[0]
    row = asyncio.run(harness.run_one(Broken(), case, "C", 0, timeout=5))
    assert row["status"] == "failed" and "boom" in row["error"]
