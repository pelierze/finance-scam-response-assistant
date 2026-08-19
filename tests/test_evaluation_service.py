import json
from collections import Counter
from pathlib import Path

import pytest

from src.evaluation_service import (
    EVALUATION_CATEGORIES,
    evaluate_extractor,
    load_evaluation_cases,
)
from src.local_extractor import LocalKoreanRuleExtractor

DATASET = Path(__file__).parents[1] / "data" / "evaluation_cases.json"


def test_dataset_has_45_balanced_labeled_cases() -> None:
    cases = load_evaluation_cases(DATASET)

    assert len(cases) == 45
    assert Counter(case.category for case in cases) == {
        category: 3 for category in EVALUATION_CATEGORIES
    }


def test_every_case_has_unique_id_and_consistent_ground_truth() -> None:
    cases = load_evaluation_cases(DATASET)

    assert len({case.id for case in cases}) == len(cases)
    assert all(case.expected_analysis() for case in cases)


def test_local_evaluation_report_covers_every_case_and_category() -> None:
    cases = load_evaluation_cases(DATASET)
    report = evaluate_extractor(cases, LocalKoreanRuleExtractor())

    assert report.total_cases == 45
    assert set(report.category_exact_accuracy) == EVALUATION_CATEGORIES
    assert 0 <= report.exact_case_accuracy <= 1
    assert 0 <= report.done_precision <= 1
    assert 0 <= report.done_recall <= 1
    assert 0 <= report.done_f1 <= 1
    assert 0 <= report.question_exact_accuracy <= 1


def test_loader_rejects_ground_truth_that_conflicts_with_level(tmp_path) -> None:
    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    raw[0]["expected_level"] = 5
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="level conflicts"):
        load_evaluation_cases(invalid)
