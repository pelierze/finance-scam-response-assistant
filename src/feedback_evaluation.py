"""Score the reviewed 50-case feedback suite for local and LLM extractors."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.analyzer import StructuredExtractor, analyze_text
from src.models import TRACKED_ACTIONS, ActionStatus
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
    redacted_input: str | None = None

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
            "redacted_input": self.redacted_input,
        }


def run_feedback_cases(
    cases: list[dict[str, Any]],
    extractor: StructuredExtractor,
    guides: tuple[ResponseGuide, ...],
    *,
    max_attempts: int = 2,
) -> list[FeedbackRun]:
    runs: list[FeedbackRun] = []
    for case in cases:
        result = analyze_text(case["input"], extractor, max_attempts=max_attempts)
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
                redacted_input=result.redacted_text,
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


def load_guide_expectations(
    path: str | Path,
    *,
    case_ids: set[str],
    guide_ids: set[str],
) -> dict[str, dict[str, frozenset[str]]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Guide evaluation labels must be a non-empty list")
    expectations: dict[str, dict[str, frozenset[str]]] = {}
    for item in raw:
        if set(item) != {"id", "required_guide_ids", "forbidden_guide_ids"}:
            raise ValueError("Guide evaluation label fields do not match the schema")
        case_id = item["id"]
        if case_id not in case_ids or case_id in expectations:
            raise ValueError(f"Unknown or duplicate guide case ID: {case_id}")
        required = frozenset(item["required_guide_ids"])
        forbidden = frozenset(item["forbidden_guide_ids"])
        if required & forbidden:
            raise ValueError(f"Guide labels overlap: {case_id}")
        if (required | forbidden) - guide_ids:
            raise ValueError(f"Unknown guide ID in labels: {case_id}")
        expectations[case_id] = {"required": required, "forbidden": forbidden}
    return expectations


def score_feedback_runs(
    cases: list[dict[str, Any]],
    runs: list[FeedbackRun],
    guides: tuple[ResponseGuide, ...],
    guide_expectations: dict[str, dict[str, frozenset[str]]] | None = None,
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
    forbidden_guide_hits = forbidden_guide_total = 0
    explicitly_labeled_guide_cases = 0
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

        explicit_guides = (
            guide_expectations.get(case["id"]) if guide_expectations else None
        )
        if explicit_guides is not None:
            explicitly_labeled_guide_cases += 1
            expected_guides = set(explicit_guides["required"])
            forbidden_guides = set(explicit_guides["forbidden"])
        elif guide_expectations is None and case.get("expected_level", 0) >= 3:
            expected_guides = _expected_guide_ids(case, guides)
            forbidden_guides = set()
        else:
            expected_guides = set()
            forbidden_guides = set()
        if expected_guides or forbidden_guides:
            actual_guides = set(run.guide_ids)
            required_guides_total += len(expected_guides)
            missing_guides = expected_guides - actual_guides
            required_guides_missing += len(missing_guides)
            failures.extend(f"missing guide: {guide_id}" for guide_id in missing_guides)
            forbidden_guide_total += len(forbidden_guides)
            unexpected_guides = forbidden_guides & actual_guides
            forbidden_guide_hits += len(unexpected_guides)
            failures.extend(
                f"forbidden guide: {guide_id}" for guide_id in unexpected_guides
            )

        if run.used_fallback:
            failures.append(f"fallback: {run.error_code}")
        case_passes += int(not failures)
        if failures:
            stages: set[str] = set()
            for failure in failures:
                if any(failure.startswith(f"{action}:") for action in TRACKED_ACTIONS):
                    stages.add("llm_extraction")
                elif "exposure" in failure or failure.startswith("level:"):
                    stages.add("rule_engine")
                elif "question" in failure:
                    stages.add("question_engine")
                elif "redaction" in failure:
                    stages.add("redaction")
                elif "guide" in failure:
                    stages.add("guide_composition")
                elif failure == "fallback: invalid_model_output":
                    stages.add("schema_validation")
                elif failure.startswith("fallback:"):
                    stages.add("provider_or_fallback")
            failed_cases.append(
                {"id": case["id"], "stages": sorted(stages), "failures": failures}
            )

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
        "forbidden_guide_incidence": ratio(
            forbidden_guide_hits, forbidden_guide_total
        ),
        "forbidden_guide_labels": forbidden_guide_total,
        "explicitly_labeled_guide_cases": explicitly_labeled_guide_cases,
        "failed_cases": failed_cases,
    }
