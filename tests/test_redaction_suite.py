from pathlib import Path

from src.redaction_suite import load_and_evaluate_redaction_suite

ROOT = Path(__file__).parents[1]
GENERAL_DATASET = ROOT / "data" / "redaction_evaluation_cases.json"
BANK_DATASET = (
    ROOT
    / "data"
    / "feedback"
    / "reviewed"
    / "bank-account-redaction-inputs.txt"
)


def test_submission_redaction_suite_metrics() -> None:
    report = load_and_evaluate_redaction_suite(GENERAL_DATASET, BANK_DATASET)

    assert report["dataset"] == {
        "general_cases": 70,
        "bank_account_cases": 63,
        "total_cases": 133,
    }
    assert {
        name: (group["passed_cases"], group["total_cases"])
        for name, group in report["groups"].items()
    } == {
        "basic_001_015": (15, 15),
        "advanced_016_030": (15, 15),
        "stress_031_060": (30, 30),
        "preservation_061_070": (10, 10),
        "bank_accounts": (63, 63),
    }
    metrics = report["metrics"]
    assert metrics["case_pass_rate"] == 1
    assert metrics["sensitive_detection_success_rate"] == 1
    assert metrics["sensitive_omission_rate"] == 0
    assert metrics["over_masking_rate"] == 0
    assert metrics["complex_case_pass_rate"] == 1
    assert metrics["redaction_count_accuracy"] == 1
    assert metrics["required_text_preservation_rate"] == 1
    assert report["failed_cases"] == []


def test_submission_redaction_suite_reports_every_type() -> None:
    report = load_and_evaluate_redaction_suite(GENERAL_DATASET, BANK_DATASET)

    assert set(report["types"]) == {
        "resident_id",
        "phone",
        "email",
        "card",
        "account",
        "auth_code",
        "password",
    }
    assert all(
        result["expected"] > 0
        and result["detected"] == result["expected"]
        and result["success_rate"] == 1
        for result in report["types"].values()
    )
