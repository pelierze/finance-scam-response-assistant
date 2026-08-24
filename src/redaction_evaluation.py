"""Load and score synthetic sensitive-data redaction cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.privacy_filter import redact_sensitive_text

SUPPORTED_TYPES = frozenset(
    {"resident_id", "phone", "email", "card", "auth_code", "password", "account"}
)


@dataclass(frozen=True)
class RedactionCase:
    id: str
    input: str
    expected_redacted_types: frozenset[str]
    forbidden_redacted_types: frozenset[str]
    expected_redaction_count: int
    expected_unmasked_contains: tuple[str, ...]


def load_redaction_cases(path: str | Path) -> tuple[RedactionCase, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Redaction evaluation dataset must be a non-empty list")
    cases: list[RedactionCase] = []
    required = {
        "id",
        "input",
        "expected_redacted_types",
        "forbidden_redacted_types",
        "expected_redaction_count",
        "expected_unmasked_contains",
    }
    for item in raw:
        if set(item) != required:
            raise ValueError("Redaction case fields do not match the schema")
        expected = frozenset(item["expected_redacted_types"])
        forbidden = frozenset(item["forbidden_redacted_types"])
        if (expected | forbidden) - SUPPORTED_TYPES:
            raise ValueError(f"Unsupported redaction type: {item['id']}")
        if expected & forbidden:
            raise ValueError(f"Expected and forbidden types overlap: {item['id']}")
        count = item["expected_redaction_count"]
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"Invalid redaction count: {item['id']}")
        preserved = tuple(item["expected_unmasked_contains"])
        if any(fragment not in item["input"] for fragment in preserved):
            raise ValueError(f"Preserved fragment is absent from input: {item['id']}")
        cases.append(
            RedactionCase(
                id=item["id"],
                input=item["input"],
                expected_redacted_types=expected,
                forbidden_redacted_types=forbidden,
                expected_redaction_count=count,
                expected_unmasked_contains=preserved,
            )
        )
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Redaction case IDs must be unique")
    return tuple(cases)


def evaluate_redaction_cases(cases: tuple[RedactionCase, ...]) -> dict[str, Any]:
    type_matches = count_matches = preserved_matches = 0
    preserved_total = 0
    forbidden_hits = 0
    forbidden_total = 0
    failures: list[dict[str, Any]] = []

    for case in cases:
        result = redact_sensitive_text(case.input)
        actual_types = frozenset(result.detected_types)
        case_failures: list[str] = []
        types_match = actual_types == case.expected_redacted_types
        type_matches += int(types_match)
        if not types_match:
            case_failures.append(
                "types: expected="
                f"{sorted(case.expected_redacted_types)}, actual={sorted(actual_types)}"
            )
        forbidden_total += len(case.forbidden_redacted_types)
        hits = actual_types & case.forbidden_redacted_types
        forbidden_hits += len(hits)
        if hits:
            case_failures.append(f"forbidden types: {sorted(hits)}")
        count_match = result.redaction_count == case.expected_redaction_count
        count_matches += int(count_match)
        if not count_match:
            case_failures.append(
                f"count: expected={case.expected_redaction_count}, "
                f"actual={result.redaction_count}"
            )
        for fragment in case.expected_unmasked_contains:
            preserved_total += 1
            preserved = fragment in result.text
            preserved_matches += int(preserved)
            if not preserved:
                case_failures.append(f"required text was masked: {fragment}")
        if case_failures:
            failures.append({"id": case.id, "failures": case_failures})

    total = len(cases)
    passed = total - len(failures)
    return {
        "total_cases": total,
        "case_pass_rate": passed / total,
        "type_exact_accuracy": type_matches / total,
        "redaction_count_accuracy": count_matches / total,
        "required_text_preservation_rate": (
            preserved_matches / preserved_total if preserved_total else None
        ),
        "forbidden_type_incidence": (
            forbidden_hits / forbidden_total if forbidden_total else None
        ),
        "redaction_labels": sum(case.expected_redaction_count for case in cases),
        "preservation_labels": preserved_total,
        "failed_cases": failures,
    }
