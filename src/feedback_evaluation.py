"""Score the reviewed 50-case feedback suite for local and LLM extractors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.analyzer import StructuredExtractor, analyze_text
from src.models import ActionStatus
from src.question_engine import select_questions
from src.response_service import ResponseGuide, compose_guides
from src.rule_engine import assess_exposure


@dataclass(frozen=True)
class FeedbackRun:
    case_id: str
    actions: dict[str, str]
    active_dimensions: tuple[str, ...]
    level: int
    questions: tuple[str, ...]
    redacted_types: tuple[str, ...]
    guide_ids: tuple[str, ...]
    used_fallback: bool
    error_code: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "actions": self.actions,
            "active_dimensions": list(self.active_dimensions),
            "level": self.level,
            "questions": list(self.questions),
            "redacted_types": list(self.redacted_types),
            "guide_ids": list(self.guide_ids),
            "used_fallback": self.used_fallback,
            "error_code": self.error_code,
        }


def run_feedback_cases(
    cases: list[dict[str, Any]],
    extractor: StructuredExtractor,
    guides: tuple[ResponseGuide, ...],
) -> list[FeedbackRun]:
    runs: list[FeedbackRun] = []
    for case in cases:
        result = analyze_text(case["input"], extractor)
        assessment = assess_exposure(result.analysis)
        runs.append(
            FeedbackRun(
                case_id=case["id"],
                actions={
                    action: observation.status.value
                    for action, observation in result.analysis.actions.items()
                },
                active_dimensions=tuple(sorted(assessment.active_dimensions)),
                level=int(assessment.representative_level),
                questions=tuple(
                    question.action for question in select_questions(result.analysis)
                ),
                redacted_types=tuple(sorted(result.redacted_types)),
                guide_ids=tuple(
                    guide.action_id for guide in compose_guides(assessment, guides)
                ),
                used_fallback=result.used_fallback,
                error_code=result.error_code,
            )
        )
    return runs


def _expected_guide_ids(
    case: dict[str, Any], guides: tuple[ResponseGuide, ...]
) -> set[str]:
    done_actions = {
        action
        for action, status in case["expected_actions"].items()
        if status == ActionStatus.DONE.value
    }
    return {
        guide.action_id for guide in guides if guide.applies_when & done_actions
    }


def score_feedback_runs(
    cases: list[dict[str, Any]],
    runs: list[FeedbackRun],
    guides: tuple[ResponseGuide, ...],
) -> dict[str, Any]:
    if [case["id"] for case in cases] != [run.case_id for run in runs]:
        raise ValueError("Cases and runs must have the same IDs in the same order")

    action_correct = action_total = 0
    exposure_correct = exposure_total = 0
    level_correct = level_total = 0
    required_question_correct = required_question_total = 0
    forbidden_question_hits = forbidden_question_total = 0
    masking_correct = masking_total = 0
    required_guides_missing = required_guides_total = 0
    case_passes = 0
    failed_cases: list[dict[str, Any]] = []

    for case, run in zip(cases, runs, strict=True):
        failures: list[str] = []
        for action, expected in case["expected_actions"].items():
            action_total += 1
            matched = run.actions[action] == expected
            action_correct += int(matched)
            if not matched:
                failures.append(
                    f"{action}: expected={expected}, actual={run.actions[action]}"
                )

        actual_exposures = set(run.active_dimensions)
        for dimension in case.get("expected_exposures", []):
            exposure_total += 1
            matched = dimension in actual_exposures
            exposure_correct += int(matched)
            if not matched:
                failures.append(f"missing exposure: {dimension}")
        for dimension in case.get("forbidden_exposures", []):
            exposure_total += 1
            matched = dimension not in actual_exposures
            exposure_correct += int(matched)
            if not matched:
                failures.append(f"forbidden exposure: {dimension}")

        if "expected_level" in case:
            level_total += 1
            matched = run.level == case["expected_level"]
            level_correct += int(matched)
            if not matched:
                failures.append(
                    f"level: expected={case['expected_level']}, actual={run.level}"
                )

        actual_questions = set(run.questions)
        for action in case.get("expected_questions", []):
            required_question_total += 1
            matched = action in actual_questions
            required_question_correct += int(matched)
            if not matched:
                failures.append(f"missing question: {action}")
        for action in case.get("forbidden_questions", []):
            forbidden_question_total += 1
            hit = action in actual_questions
            forbidden_question_hits += int(hit)
            if hit:
                failures.append(f"forbidden question: {action}")

        actual_redactions = set(run.redacted_types)
        for redaction_type in case.get("expected_redacted_types", []):
            masking_total += 1
            matched = redaction_type in actual_redactions
            masking_correct += int(matched)
            if not matched:
                failures.append(f"missing redaction: {redaction_type}")
        for redaction_type in case.get("forbidden_redacted_types", []):
            masking_total += 1
            matched = redaction_type not in actual_redactions
            masking_correct += int(matched)
            if not matched:
                failures.append(f"forbidden redaction: {redaction_type}")

        if case.get("expected_level", 0) >= 3:
            expected_guides = _expected_guide_ids(case, guides)
            actual_guides = set(run.guide_ids)
            required_guides_total += len(expected_guides)
            missing_guides = expected_guides - actual_guides
            required_guides_missing += len(missing_guides)
            failures.extend(f"missing guide: {guide_id}" for guide_id in missing_guides)

        if run.used_fallback:
            failures.append(f"fallback: {run.error_code}")
        case_passes += int(not failures)
        if failures:
            failed_cases.append({"id": case["id"], "failures": failures})

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    return {
        "total_cases": len(cases),
        "successful_analysis_cases": sum(not run.used_fallback for run in runs),
        "fallback_cases": sum(run.used_fallback for run in runs),
        "case_pass_rate": ratio(case_passes, len(cases)),
        "action_status_accuracy": ratio(action_correct, action_total),
        "action_status_labels": action_total,
        "exposure_accuracy": ratio(exposure_correct, exposure_total),
        "exposure_labels": exposure_total,
        "level_accuracy": ratio(level_correct, level_total),
        "required_question_accuracy": ratio(
            required_question_correct, required_question_total
        ),
        "required_question_labels": required_question_total,
        "forbidden_question_incidence": ratio(
            forbidden_question_hits, forbidden_question_total
        ),
        "forbidden_question_labels": forbidden_question_total,
        "masking_success_rate": ratio(masking_correct, masking_total),
        "masking_labels": masking_total,
        "high_risk_required_guide_omission_rate": ratio(
            required_guides_missing, required_guides_total
        ),
        "high_risk_required_guide_labels": required_guides_total,
        "failed_cases": failed_cases,
    }
