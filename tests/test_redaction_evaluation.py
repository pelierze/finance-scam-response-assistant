from pathlib import Path

from src.redaction_evaluation import evaluate_redaction_cases, load_redaction_cases

DATASET = Path(__file__).parents[1] / "data" / "redaction_evaluation_cases.json"


def test_redaction_evaluation_dataset_is_complete_and_synthetic() -> None:
    cases = load_redaction_cases(DATASET)

    assert [case.id for case in cases] == [
        f"REDACTION-{number:03d}" for number in range(1, 16)
    ]
    assert {data_type for case in cases for data_type in case.expected_types} == {
        "resident_id",
        "phone",
        "email",
        "card",
        "auth_secret",
        "account",
    }


def test_redaction_evaluation_has_no_leaks_or_false_positives() -> None:
    report = evaluate_redaction_cases(load_redaction_cases(DATASET))

    assert report["type_exact_accuracy"] == 1
    assert report["masking_success_rate"] == 1
    assert report["sensitive_value_leak_rate"] == 0
    assert report["placeholder_success_rate"] == 1
    assert report["false_positive_case_rate"] == 0
    assert report["failed_cases"] == []
