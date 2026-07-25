from knowflow.evaluation.runner import run_evaluation


def test_hash_evaluation_runs_without_cloud_calls() -> None:
    result = run_evaluation(embedding_backend="hash", top_k=6)
    assert result["dataset_cases"] == 56
    assert result["dense"]["cases"] == 33
    assert 0 <= result["dense"]["recall_at_k"] <= 1
    assert 0 <= result["hybrid"]["recall_at_k"] <= 1
    assert result["retrieval_source_checks"] > 0
    assert 0 <= result["retrieval_source_integrity"] <= 1
    assert (
        result["retrieval_source_integrity"]
        == result["hybrid"]["retrieval_source_integrity"]
    )
    assert result["citation_correctness"] == "待测量"
    assert result["cloud_metrics"]["answer_faithfulness"] == "待测量"
