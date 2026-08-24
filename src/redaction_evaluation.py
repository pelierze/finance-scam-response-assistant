"""Load and score synthetic sensitive-data redaction cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.privacy_filter import redact_sensitive_text

SUPPORTED_TYPES = frozenset(
    {"resident_id", "phone", "email", "card", "auth_secret", "account"}
)


@dataclass(frozen=True)
class RedactionCase:
    id: str
    text: str
    expected_types: frozenset[str]
    sensitive_fragments: tuple[str, ...]
    expected_placeholders: tuple[str, ...]


def load_redaction_cases(path: str | Path) -> tuple[RedactionCase, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Redaction evaluation dataset must be a non-empty list")
    cases: list[RedactionCase] = []
    for item in raw:
        if set(item) != {
            "id",
            "text",
            "expected_types",
            "sensitive_fragments",
            "expected_placeholders",
        }:
            raise ValueError("Redaction case fields do not match the schema")
        expected_types = frozenset(item["expected_types"])
        if expected_types - SUPPORTED_TYPES:
            raise ValueError(f"Unsupported redaction type: {item['id']}")
        if any(fragment not in item["text"] for fragment in item["sensitive_fragments"]):
            raise ValueError(f"Sensitive fragment is absent from input: {item['id']}")
        cases.append(
            RedactionCase(
                id=item["id"],
                text=item["text"],
                expected_types=expected_types,
                sensitive_fragments=tuple(item["sensitive_fragments"]),
                expected_placeholders=tuple(item["expected_placeholders"]),
            )
        )
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Redaction case IDs must be unique")
    return tuple(cases)


def evaluate_redaction_cases(cases: tuple[RedactionCase, ...]) -> dict[str, Any]:
    exact_type_matches = 0
    positive_fragments = leaked_fragments = 0
    expected_placeholders = missing_placeholders = 0
    negative_cases = false_positive_cases = 0
    failures: list[dict[str, Any]] = []

    for case in cases:
        result = redact_sensitive_text(case.text)
        actual_types = frozenset(result.detected_types)
        case_failures: list[str] = []
        exact_type_matches += int(actual_types == case.expected_types)
        if actual_types != case.expected_types:
            case_failures.append(
                f"types: expected={sorted(case.expected_types)}, actual={sorted(actual_types)}"
            )
        for fragment in case.sensitive_fragments:
            positive_fragments += 1
            leaked = fragment in result.text
            leaked_fragments += int(leaked)
            if leaked:
                case_failures.append(f"sensitive fragment leaked: {fragment}")
        for placeholder in case.expected_placeholders:
            expected_placeholders += 1
            missing = placeholder not in result.text
            missing_placeholders += int(missing)
            if missing:
                case_failures.append(f"missing placeholder: {placeholder}")
        if not case.expected_types:
            negative_cases += 1
            false_positive = bool(actual_types)
            false_positive_cases += int(false_positive)
            if false_positive:
                case_failures.append("false positive redaction")
        if case_failures:
            failures.append({"id": case.id, "failures": case_failures})

    return {
        "total_cases": len(cases),
        "type_exact_accuracy": exact_type_matches / len(cases),
        "masking_success_rate": (
            (positive_fragments - leaked_fragments) / positive_fragments
            if positive_fragments
            else None
        ),
        "sensitive_value_leak_rate": (
            leaked_fragments / positive_fragments if positive_fragments else None
        ),
        "placeholder_success_rate": (
            (expected_placeholders - missing_placeholders) / expected_placeholders
            if expected_placeholders
            else None
        ),
        "false_positive_case_rate": (
            false_positive_cases / negative_cases if negative_cases else None
        ),
        "positive_fragment_labels": positive_fragments,
        "negative_cases": negative_cases,
        "failed_cases": failures,
    }
