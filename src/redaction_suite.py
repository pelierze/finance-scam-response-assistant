"""Aggregate redaction metrics across reviewed synthetic datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.privacy_filter import redact_sensitive_text
from src.redaction_evaluation import (
    SUPPORTED_TYPES,
    RedactionCase,
    evaluate_redaction_cases,
    load_redaction_cases,
)

PLACEHOLDER_BY_TYPE = {
    "resident_id": "[주민등록번호 마스킹]",
    "phone": "[전화번호 마스킹]",
    "email": "[이메일 마스킹]",
    "card": "[카드번호 마스킹]",
    "auth_code": "[인증정보 마스킹]",
    "password": "[비밀번호 마스킹]",
    "account": "[계좌번호 마스킹]",
}


def load_bank_account_cases(path: str | Path) -> tuple[RedactionCase, ...]:
    """Load one-account-per-line synthetic bank-account examples."""

    lines = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        raise ValueError("Bank-account evaluation dataset must not be empty")
    return tuple(
        RedactionCase(
            id=f"BANK-ACCOUNT-{number:03d}",
            input=line,
            expected_redacted_types=frozenset({"account"}),
            forbidden_redacted_types=SUPPORTED_TYPES - {"account"},
            expected_redaction_count=1,
            expected_masked_contains=(PLACEHOLDER_BY_TYPE["account"],),
            expected_unmasked_contains=(),
        )
        for number, line in enumerate(lines, start=1)
    )


def _group_report(cases: tuple[RedactionCase, ...]) -> dict[str, Any]:
    report = evaluate_redaction_cases(cases)
    return {
        "total_cases": report["total_cases"],
        "passed_cases": report["total_cases"] - len(report["failed_cases"]),
        "failed_cases": len(report["failed_cases"]),
        "failed_case_ids": [failure["id"] for failure in report["failed_cases"]],
        "case_pass_rate": report["case_pass_rate"],
    }


def evaluate_redaction_suite(
    general_cases: tuple[RedactionCase, ...],
    bank_cases: tuple[RedactionCase, ...],
) -> dict[str, Any]:
    """Return submission-facing detection, omission and over-masking metrics."""

    groups = {
        "basic_001_015": general_cases[:15],
        "advanced_016_030": general_cases[15:30],
        "stress_031_060": general_cases[30:60],
        "preservation_061_070": general_cases[60:70],
        "bank_accounts": bank_cases,
    }
    all_cases = general_cases + bank_cases
    overall = evaluate_redaction_cases(all_cases)

    expected_by_type = {data_type: 0 for data_type in sorted(SUPPORTED_TYPES)}
    detected_by_type = {data_type: 0 for data_type in sorted(SUPPORTED_TYPES)}
    forbidden_labels = forbidden_hits = 0
    preservation_labels = preservation_failures = 0

    for case in all_cases:
        result = redact_sensitive_text(case.input)
        actual = set(result.detected_types)
        for data_type in case.expected_redacted_types:
            expected_by_type[data_type] += 1
            detected_by_type[data_type] += int(data_type in actual)
        forbidden_labels += len(case.forbidden_redacted_types)
        forbidden_hits += len(actual & case.forbidden_redacted_types)
        preservation_labels += len(case.expected_unmasked_contains)
        preservation_failures += sum(
            fragment not in result.text for fragment in case.expected_unmasked_contains
        )

    expected_labels = sum(expected_by_type.values())
    detected_labels = sum(detected_by_type.values())
    omitted_labels = expected_labels - detected_labels
    over_masking_denominator = forbidden_labels + preservation_labels
    over_masking_events = forbidden_hits + preservation_failures
    complex_cases = tuple(
        case for case in all_cases if len(case.expected_redacted_types) >= 2
    )
    complex_report = evaluate_redaction_cases(complex_cases)

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "dataset": {
            "general_cases": len(general_cases),
            "bank_account_cases": len(bank_cases),
            "total_cases": len(all_cases),
        },
        "groups": {name: _group_report(cases) for name, cases in groups.items()},
        "metrics": {
            "case_pass_rate": overall["case_pass_rate"],
            "sensitive_detection_success_rate": ratio(
                detected_labels, expected_labels
            ),
            "sensitive_detection_labels": expected_labels,
            "sensitive_omission_rate": ratio(omitted_labels, expected_labels),
            "sensitive_omissions": omitted_labels,
            "over_masking_rate": ratio(
                over_masking_events, over_masking_denominator
            ),
            "over_masking_events": over_masking_events,
            "over_masking_labels": over_masking_denominator,
            "forbidden_type_hits": forbidden_hits,
            "preservation_failures": preservation_failures,
            "complex_case_pass_rate": complex_report["case_pass_rate"],
            "complex_cases": len(complex_cases),
            "redaction_count_accuracy": overall["redaction_count_accuracy"],
            "required_text_preservation_rate": overall[
                "required_text_preservation_rate"
            ],
        },
        "types": {
            data_type: {
                "detected": detected_by_type[data_type],
                "expected": expected_by_type[data_type],
                "success_rate": ratio(
                    detected_by_type[data_type], expected_by_type[data_type]
                ),
            }
            for data_type in sorted(SUPPORTED_TYPES)
        },
        "failed_cases": overall["failed_cases"],
    }


def load_and_evaluate_redaction_suite(
    general_path: str | Path, bank_path: str | Path
) -> dict[str, Any]:
    return evaluate_redaction_suite(
        load_redaction_cases(general_path), load_bank_account_cases(bank_path)
    )
