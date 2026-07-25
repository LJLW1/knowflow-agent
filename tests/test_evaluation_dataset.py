import json
from collections import Counter
from pathlib import Path


def test_evaluation_dataset_has_exactly_56_unique_cases() -> None:
    path = Path(__file__).parents[1] / "evaluation" / "questions.jsonl"
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    counts = Counter(case["category"] for case in cases)
    assert len(cases) == 56
    assert len({case["id"] for case in cases}) == 56
    assert counts == {
        "direct": 15,
        "cross_document": 8,
        "absent": 8,
        "hallucination": 5,
        "tool_call": 8,
        "multi_step": 6,
        "tool_failure": 6,
    }
    assert all("expected_documents" in case for case in cases)
