"""Load labeled natural-language cases and score structured extractors."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.analyzer import StructuredExtractor, analyze_text
from src.models import TRACKED_ACTIONS, ActionStatus, StructuredAnalysis
from src.question_engine import QUESTION_CATALOG, select_questions
from src.rule_engine import assess_exposure

EVALUATION_CATEGORIES = frozenset(
    {
        "suspicious_contact",
        "link_clicked",
        "app_installed",
        "personal_info_shared",
        "financial_info_shared",
        "auth_info_shared",
        "money_transferred",
        "compound_harm",
        "negation",
        "uncertain",
        "contradiction",
        "typo_colloquial",
        "irrelevant",
        "sensitive_data",
        "prompt_injection",
    }
)
REDACTION_TYPES = frozenset(
    {"resident_id", "phone", "email", "card", "auth_secret", "account"}
)


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    category: str
    text: str
    expected_actions: dict[str, ActionStatus]
    expected_dimensions: frozenset[str]
    expected_level: int
    expected_questions: frozenset[str]
    expected_redacted_types: frozenset[str]

    def expected_analysis(self) -> StructuredAnalysis:
        actions = {
            action: {
                "status": self.expected_actions.get(
                    action, ActionStatus.NOT_MENTIONED
                ).value,
                "evidence": (
                    self.text
                    if self.expected_actions.get(action) is ActionStatus.DONE
                    else None
                ),
            }
            for action in TRACKED_ACTIONS
        }
        return StructuredAnalysis.from_dict(
            {"impersonated_entity": None, "risk_signals": [], "actions": actions}
        )


@dataclass(frozen=True)
class EvaluationReport:
    total_cases: int
    action_accuracy: float
    exact_case_accuracy: float
    done_precision: float
    done_recall: float
    done_f1: float
    dimension_exact_accuracy: float
    level_accuracy: float
    question_exact_accuracy: float
    redaction_exact_accuracy: float
    category_exact_accuracy: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "action_accuracy": self.action_accuracy,
            "exact_case_accuracy": self.exact_case_accuracy,
            "done_precision": self.done_precision,
            "done_recall": self.done_recall,
            "done_f1": self.done_f1,
            "dimension_exact_accuracy": self.dimension_exact_accuracy,
            "level_accuracy": self.level_accuracy,
            "question_exact_accuracy": self.question_exact_accuracy,
            "redaction_exact_accuracy": self.redaction_exact_accuracy,
            "category_exact_accuracy": self.category_exact_accuracy,
        }


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Evaluation case {field} must be a non-empty string")
    return value


def _parse_case(value: Any) -> EvaluationCase:
    required = {
        "id",
        "category",
        "text",
        "actions",
        "expected_dimensions",
        "expected_level",
        "expected_questions",
        "expected_redacted_types",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Evaluation case fields do not match the required schema")
    case_id = _required_string(value["id"], "id")
    category = _required_string(value["category"], "category")
    text = _required_string(value["text"], "text")
    if category not in EVALUATION_CATEGORIES:
        raise ValueError(f"Unknown evaluation category: {category}")
    if not isinstance(value["actions"], dict):
        raise TypeError("Evaluation actions must be an object")
    unknown_actions = set(value["actions"]) - set(TRACKED_ACTIONS)
    if unknown_actions:
        raise ValueError(f"Unknown evaluation actions: {sorted(unknown_actions)}")
    try:
        actions = {
            action: ActionStatus(status)
            for action, status in value["actions"].items()
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Evaluation action status is invalid") from exc
    dimensions = frozenset(value["expected_dimensions"])
    level = value["expected_level"]
    questions = frozenset(value["expected_questions"])
    redacted_types = frozenset(value["expected_redacted_types"])
    if not isinstance(level, int) or level not in range(6):
        raise ValueError("Expected level must be an integer from zero to five")
    if questions - set(QUESTION_CATALOG):
        raise ValueError("Expected questions contain an unsupported action")
    if redacted_types - REDACTION_TYPES:
        raise ValueError("Expected redaction types contain an unsupported value")
    case = EvaluationCase(
        id=case_id,
        category=category,
        text=text,
        expected_actions=actions,
        expected_dimensions=dimensions,
        expected_level=level,
        expected_questions=questions,
        expected_redacted_types=redacted_types,
    )
    assessment = assess_exposure(case.expected_analysis())
    if assessment.active_dimensions != dimensions:
        raise ValueError(f"Expected dimensions conflict with action labels: {case_id}")
    if int(assessment.representative_level) != level:
        raise ValueError(f"Expected level conflicts with action labels: {case_id}")
    return case


def load_evaluation_cases(path: str | Path) -> tuple[EvaluationCase, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Evaluation dataset must be a non-empty list")
    cases = tuple(_parse_case(value) for value in raw)
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique")
    return cases


def evaluate_extractor(
    cases: tuple[EvaluationCase, ...], extractor: StructuredExtractor
) -> EvaluationReport:
    action_matches = 0
    action_total = len(cases) * len(TRACKED_ACTIONS)
    exact_cases = 0
    expected_done = 0
    predicted_done = 0
    predicted_done_correctly = 0
    dimension_matches = 0
    level_matches = 0
    question_matches = 0
    redaction_matches = 0
    category_totals: Counter[str] = Counter()
    category_exact: defaultdict[str, int] = defaultdict(int)

    for case in cases:
        result = analyze_text(case.text, extractor)
        predicted = result.analysis
        expected = case.expected_analysis()
        matches = [
            predicted.actions[action].status is expected.actions[action].status
            for action in TRACKED_ACTIONS
        ]
        action_matches += sum(matches)
        is_exact = all(matches)
        exact_cases += int(is_exact)
        category_totals[case.category] += 1
        category_exact[case.category] += int(is_exact)
        for action in TRACKED_ACTIONS:
            predicted_done += int(
                predicted.actions[action].status is ActionStatus.DONE
            )
            if expected.actions[action].status is ActionStatus.DONE:
                expected_done += 1
                predicted_done_correctly += int(
                    predicted.actions[action].status is ActionStatus.DONE
                )
        assessment = assess_exposure(predicted)
        dimension_matches += int(
            assessment.active_dimensions == case.expected_dimensions
        )
        level_matches += int(
            int(assessment.representative_level) == case.expected_level
        )
        predicted_questions = frozenset(
            question.action for question in select_questions(predicted)
        )
        question_matches += int(predicted_questions == case.expected_questions)
        redaction_matches += int(
            frozenset(result.redacted_types) == case.expected_redacted_types
        )

    total = len(cases)
    done_precision = predicted_done_correctly / predicted_done if predicted_done else 0
    done_recall = predicted_done_correctly / expected_done if expected_done else 0
    done_f1 = (
        2 * done_precision * done_recall / (done_precision + done_recall)
        if done_precision + done_recall
        else 0
    )
    return EvaluationReport(
        total_cases=total,
        action_accuracy=action_matches / action_total,
        exact_case_accuracy=exact_cases / total,
        done_precision=done_precision,
        done_recall=done_recall,
        done_f1=done_f1,
        dimension_exact_accuracy=dimension_matches / total,
        level_accuracy=level_matches / total,
        question_exact_accuracy=question_matches / total,
        redaction_exact_accuracy=redaction_matches / total,
        category_exact_accuracy={
            category: category_exact[category] / count
            for category, count in sorted(category_totals.items())
        },
    )
