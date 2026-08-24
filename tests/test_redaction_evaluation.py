from pathlib import Path

from src.redaction_evaluation import evaluate_redaction_cases, load_redaction_cases

DATASET = Path(__file__).parents[1] / "data" / "redaction_evaluation_cases.json"


def test_redaction_evaluation_dataset_is_complete_and_synthetic() -> None:
    cases = load_redaction_cases(DATASET)

    assert [case.id for case in cases] == [
        f"REDACT-{number:03d}" for number in range(1, 31)
    ]
    assert {
        data_type for case in cases for data_type in case.expected_redacted_types
    } == {
        "resident_id",
        "phone",
        "email",
        "card",
        "auth_code",
        "password",
        "account",
    }


def test_redaction_evaluation_has_no_leaks_or_false_positives() -> None:
    report = evaluate_redaction_cases(load_redaction_cases(DATASET))

    assert report["case_pass_rate"] == 1
    assert report["type_exact_accuracy"] == 1
    assert report["redaction_count_accuracy"] == 1
    assert report["required_text_preservation_rate"] == 1
    assert report["forbidden_type_incidence"] == 0
    assert report["redaction_labels"] == 44
    assert report["failed_cases"] == []
